#import <CoreWLAN/CoreWLAN.h>
#import <Foundation/Foundation.h>
#import <IOKit/IOKitLib.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

// These libIOReport signatures were checked on macOS build 26B131.
extern CFDictionaryRef IOReportCopyChannelsForDriver(io_service_t, CFAllocatorRef, CFErrorRef *);
extern CFStringRef IOReportChannelGetGroup(CFDictionaryRef);
extern CFStringRef IOReportChannelGetSubGroup(CFDictionaryRef);
extern CFStringRef IOReportChannelGetChannelName(CFDictionaryRef);
extern uint8_t IOReportChannelGetFormat(CFDictionaryRef);
extern uint64_t IOReportChannelGetDriverID(CFDictionaryRef);
extern uint64_t IOReportChannelGetUnit(CFDictionaryRef);
extern CFTypeRef IOReportCreateSubscription(void *, CFMutableDictionaryRef, CFMutableDictionaryRef *, uint64_t, CFErrorRef *);
extern CFDictionaryRef IOReportCreateSamples(CFTypeRef, CFMutableDictionaryRef, CFErrorRef *);
extern int64_t IOReportSimpleGetIntegerValue(CFDictionaryRef, uint64_t *);
extern int IOReportStateGetCount(CFDictionaryRef);
extern CFStringRef IOReportStateGetNameForIndex(CFDictionaryRef, int);
extern int64_t IOReportStateGetResidency(CFDictionaryRef, int);
extern int64_t IOReportStateGetInTransitions(CFDictionaryRef, int);

static NSString *const ChannelList = @"IOReportChannels";
static NSString *const ExternalCCA = @"CCA (%) excluding own traffic";

enum ReportFormat {
    FormatSimple = 1,
    FormatState = 2,
};

static NSDictionary *readWLANReportCatalogue(uint64_t *driverID)
{
    io_iterator_t iterator = IO_OBJECT_NULL;
    IOReturn status = IOServiceGetMatchingServices(kIOMainPortDefault,
        IOServiceNameMatching("IO80211ReporterProxy"), &iterator);
    if (status != KERN_SUCCESS) {
        return nil;
    }
    io_service_t proxy = IOIteratorNext(iterator);
    io_service_t extra = IOIteratorNext(iterator);
    IOObjectRelease(iterator);
    if (extra) {
        IOObjectRelease(extra);
    }

    NSDictionary *catalogue = nil;
    if (proxy) {
        if (!extra && IORegistryEntryGetRegistryEntryID(proxy, driverID) == KERN_SUCCESS) {
            catalogue = CFBridgingRelease(IOReportCopyChannelsForDriver(proxy, NULL, NULL));
        }
        IOObjectRelease(proxy);
    }
    return [catalogue[ChannelList] isKindOfClass:[NSArray class]] ? catalogue : nil;
}

static BOOL isSelectedChannel(CFDictionaryRef row, uint64_t driverID, BOOL wmeOnly)
{
    if (IOReportChannelGetDriverID(row) != driverID) {
        return NO;
    }
    NSString *group = (__bridge NSString *)IOReportChannelGetGroup(row);
    NSString *subgroup = (__bridge NSString *)IOReportChannelGetSubGroup(row);
    NSString *name = (__bridge NSString *)IOReportChannelGetChannelName(row);
    if (wmeOnly) {
        NSString *label = [name stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
        return [subgroup isEqualToString:@"Counters"] &&
            (([group hasPrefix:@"Tx MPDU WME Slice "] && [label hasPrefix:@"Tx MPDU Tid"]) ||
             ([group hasPrefix:@"Rx MPDU WME Slice "] && [label hasPrefix:@"Rx MPDU Tid"]));
    }
    if ([group isEqualToString:@"Channel"]) {
        return [subgroup isEqualToString:@"CCA State"] || [subgroup isEqualToString:@"CCA Last Reported"];
    }
    if ([group isEqualToString:@"Interface en0"] || [group isEqualToString:@"Interface awdl0"]) {
        return [subgroup containsString:@"CCA"] || [subgroup hasPrefix:@"QBSS"];
    }
    return [group hasPrefix:@"Interface en0 Peer "] && [name isEqualToString:ExternalCCA];
}

static id reportInteger(int64_t value)
{
    return value == INT64_MIN ? (id)[NSNull null] : @(value);
}

static NSDictionary *decodeReport(CFDictionaryRef row, BOOL wmeOnly)
{
    NSString *group = (__bridge NSString *)IOReportChannelGetGroup(row);
    NSString *name = (__bridge NSString *)IOReportChannelGetChannelName(row);
    if (wmeOnly) {
        name = [name stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    }
    uint8_t format = IOReportChannelGetFormat(row);
    NSMutableDictionary *report = [@{
        @"group": [name isEqualToString:ExternalCCA] ? @"Interface en0" : group ?: @"",
        @"subgroup": (__bridge NSString *)IOReportChannelGetSubGroup(row) ?: @"",
        @"name": name ?: @"",
        @"format": @(format),
        @"unit_raw_hex": [NSString stringWithFormat:@"0x%016llx", (unsigned long long)IOReportChannelGetUnit(row)],
    } mutableCopy];

    if (format == FormatSimple) {
        report[@"value"] = reportInteger(IOReportSimpleGetIntegerValue(row, NULL));
    } else if (format == FormatState) {
        NSMutableArray *states = [NSMutableArray array];
        int count = IOReportStateGetCount(row);
        for (int index = 0; index < count; ++index) {
            NSString *stateName = (__bridge NSString *)IOReportStateGetNameForIndex(row, index);
            [states addObject:@{
                @"name": stateName ?: (id)[NSNull null],
                @"residency_raw": reportInteger(IOReportStateGetResidency(row, index)),
                @"in_transitions": reportInteger(IOReportStateGetInTransitions(row, index)),
            }];
        }
        report[@"states"] = states;
    }
    return report;
}

static NSDictionary *currentLink(void)
{
    CWInterface *interface = [[CWWiFiClient sharedWiFiClient] interface];
    CWChannel *channel = interface.wlanChannel;
    NSDictionary *widthMHz = @{
        @(kCWChannelWidth20MHz): @20, @(kCWChannelWidth40MHz): @40,
        @(kCWChannelWidth80MHz): @80, @(kCWChannelWidth160MHz): @160,
    };
    return @{
        @"interface": interface.interfaceName ?: (id)[NSNull null],
        @"primary_channel": channel ? @(channel.channelNumber) : (id)[NSNull null],
        @"channel_width_mhz": widthMHz[@(channel.channelWidth)] ?: (id)[NSNull null],
    };
}

int main(int argc, char **argv)
{
    BOOL wmeOnly = argc == 2 && strcmp(argv[1], "--wme") == 0;
    if (argc != 1 && !wmeOnly) {
        fputs("Usage: read_wifi_airtime [--wme]\n", stderr);
        return 2;
    }
    @autoreleasepool {
        uint64_t driverID = 0;
        NSDictionary *catalogue = readWLANReportCatalogue(&driverID);
        NSMutableArray *requested = [NSMutableArray array];
        for (id channel in catalogue[ChannelList]) {
            if ([channel isKindOfClass:[NSDictionary class]] &&
                isSelectedChannel((__bridge CFDictionaryRef)channel, driverID, wmeOnly)) {
                [requested addObject:channel];
            }
        }
        if (requested.count == 0) {
            fprintf(stderr, "No matching WLAN %s channels in the IOReport catalogue.\n",
                wmeOnly ? "WME" : "airtime");
            return 1;
        }

        NSMutableDictionary *request = [catalogue mutableCopy];
        request[ChannelList] = requested;
        CFMutableDictionaryRef channelSet = NULL;
        CFErrorRef error = NULL;
        CFTypeRef subscription = IOReportCreateSubscription(
            NULL, (__bridge CFMutableDictionaryRef)request, &channelSet, 0, &error);
        if (!subscription || !channelSet) {
            fprintf(stderr, "IOReport subscription unavailable (%ld).\n", error ? CFErrorGetCode(error) : 0L);
            if (channelSet) CFRelease(channelSet);
            if (subscription) CFRelease(subscription);
            if (error) CFRelease(error);
            return 1;
        }
        if (error) CFRelease(error);
        error = NULL;

        NSDictionary *sample = CFBridgingRelease(IOReportCreateSamples(subscription, channelSet, &error));
        NSTimeInterval sampledAt = [[NSDate date] timeIntervalSince1970];
        if (![sample[ChannelList] isKindOfClass:[NSArray class]]) {
            fprintf(stderr, "IOReport sample unavailable (%ld).\n", error ? CFErrorGetCode(error) : 0L);
            if (error) CFRelease(error);
            CFRelease(channelSet);
            CFRelease(subscription);
            return 1;
        }
        if (error) CFRelease(error);

        NSMutableArray *reports = [NSMutableArray array];
        for (id channel in sample[ChannelList]) {
            if ([channel isKindOfClass:[NSDictionary class]] &&
                isSelectedChannel((__bridge CFDictionaryRef)channel, driverID, wmeOnly)) {
                [reports addObject:decodeReport((__bridge CFDictionaryRef)channel, wmeOnly)];
            }
        }
        CFRelease(channelSet);
        CFRelease(subscription);
        NSDictionary *result = @{
            @"sampled_at_unix_seconds": @(sampledAt),
            @"unprivileged": @((BOOL)(getuid() != 0 && geteuid() != 0)),
            @"link": currentLink(),
            @"requested_channels": @(requested.count),
            @"reports": reports,
        };
        NSData *json = [NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingSortedKeys error:NULL];
        if (!json) {
            fputs("Could not encode the IOReport sample.\n", stderr);
            return 1;
        }
        fwrite(json.bytes, 1, json.length, stdout);
        fputc('\n', stdout);
    }
    return 0;
}
