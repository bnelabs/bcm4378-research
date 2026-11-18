#import <CoreWLAN/CoreWLAN.h>
#import <AppKit/AppKit.h>
#import <Foundation/Foundation.h>
#import <IOKit/IOKitLib.h>
#import <SystemConfiguration/SystemConfiguration.h>
#include <stdlib.h>
#include <string.h>

static NSDictionary *serviceProperties(const char *name)
{
    io_service_t service = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceNameMatching(name));
    if (!service) return nil;
    CFMutableDictionaryRef properties = NULL;
    kern_return_t status = IORegistryEntryCreateCFProperties(service, &properties, kCFAllocatorDefault, 0);
    IOObjectRelease(service);
    if (status != KERN_SUCCESS) return nil;
    return CFBridgingRelease(properties);
}

static NSDictionary *channelRecord(CWChannel *channel)
{
    if (!channel) return nil;
    NSNumber *band = @{
        @(kCWChannelBand2GHz): @2, @(kCWChannelBand5GHz): @5, @(kCWChannelBand6GHz): @6
    }[@(channel.channelBand)];
    if (!band) return nil;
    NSNumber *width = @{
        @(kCWChannelWidth20MHz): @20, @(kCWChannelWidth40MHz): @40,
        @(kCWChannelWidth80MHz): @80, @(kCWChannelWidth160MHz): @160
    }[@(channel.channelWidth)];
    NSMutableDictionary *record = [@{@"band": band, @"number": @(channel.channelNumber)} mutableCopy];
    if (width) record[@"width"] = width;
    return record;
}

static NSArray<NSString *> *wiredInterfaces(void)
{
    NSArray *interfaces = CFBridgingRelease(SCNetworkInterfaceCopyAll());
    NSMutableArray<NSString *> *wired = [NSMutableArray array];
    for (id item in interfaces) {
        SCNetworkInterfaceRef interface = (__bridge SCNetworkInterfaceRef)item;
        CFStringRef type = SCNetworkInterfaceGetInterfaceType(interface);
        CFStringRef name = SCNetworkInterfaceGetBSDName(interface);
        if (type && name && CFEqual(type, kSCNetworkInterfaceTypeEthernet)) {
            [wired addObject:(__bridge NSString *)name];
        }
    }
    return wired;
}

char *kyw_mac_read(int include_channels)
{
    @autoreleasepool {
        CWInterface *interface = [CWWiFiClient sharedWiFiClient].interface;
        if (!interface.interfaceName) return NULL;
        BOOL associated = interface.interfaceMode != kCWInterfaceModeNone;
        NSMutableDictionary *result = [@{
            @"interface": interface.interfaceName,
            @"connected": @(associated),
            @"powered": @(interface.powerOn),
        } mutableCopy];
        if (associated) {
            result[@"channel"] = channelRecord(interface.wlanChannel);
            if (interface.rssiValue < 0) result[@"signal"] = @(interface.rssiValue);
            if (interface.noiseMeasurement < 0) result[@"noise"] = @(interface.noiseMeasurement);
            if (interface.transmitRate > 0) result[@"rate"] = @(interface.transmitRate);
        }
        NSDictionary *infra = serviceProperties("AppleBCMWLANSkywalkInterface");
        result[@"country"] = interface.countryCode.length ? interface.countryCode : infra[@"IO80211CountryCode"];
        if (include_channels) {
            NSDictionary *core = serviceProperties("AppleBCMWLANCore");
            if ([core[@"ChipSet"] isKindOfClass:[NSNumber class]]) {
                result[@"chip_number"] = core[@"ChipSet"];
            }
            if ([core[@"FirmwareVersion"] isKindOfClass:[NSString class]]) {
                result[@"firmware_line"] = core[@"FirmwareVersion"];
            }
            NSArray *files = core[@"RequestedFiles"];
            id first = [files isKindOfClass:[NSArray class]] ? files.firstObject : nil;
            if ([first isKindOfClass:[NSDictionary class]] && [first[@"Firmware"] isKindOfClass:[NSString class]]) {
                result[@"image"] = first[@"Firmware"];
            }
            NSMutableArray *channels = [NSMutableArray array];
            for (CWChannel *channel in interface.supportedWLANChannels) {
                NSDictionary *record = channelRecord(channel);
                if (record) [channels addObject:record];
            }
            result[@"channels"] = channels;
            if (!associated) result[@"wired"] = wiredInterfaces();
        }
        NSData *encoded = [NSJSONSerialization dataWithJSONObject:result options:0 error:NULL];
        NSString *text = [[NSString alloc] initWithData:encoded encoding:NSUTF8StringEncoding];
        return text.UTF8String ? strdup(text.UTF8String) : NULL;
    }
}

int kyw_mac_change(int power, int band, int number, int width)
{
    @autoreleasepool {
        CWInterface *interface = [CWWiFiClient sharedWiFiClient].interface;
        if (!interface || interface.interfaceMode != kCWInterfaceModeNone) return 1;
        if (power >= 0) return [interface setPower:(power != 0) error:NULL] ? 0 : 2;
        if (!interface.powerOn) return 2;
        for (CWChannel *channel in interface.supportedWLANChannels) {
            NSDictionary *record = channelRecord(channel);
            if ([record[@"band"] intValue] == band && [record[@"number"] intValue] == number &&
                [record[@"width"] intValue] == width) {
                return [interface setWLANChannel:channel error:NULL] ? 0 : 2;
            }
        }
        return 3;
    }
}

char *kyw_mac_choose_file(void)
{
    @autoreleasepool {
        NSOpenPanel *panel = [NSOpenPanel openPanel];
        panel.canChooseFiles = YES;
        panel.canChooseDirectories = NO;
        panel.allowsMultipleSelection = NO;
        if ([panel runModal] != NSModalResponseOK || !panel.URL.path.UTF8String) return NULL;
        return strdup(panel.URL.path.UTF8String);
    }
}
