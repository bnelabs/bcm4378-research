#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/IOKitLib.h>
#include <stdint.h>
#include <stdio.h>
#include <unistd.h>

// These catalogue signatures were checked against libIOReport on macOS build 26B131.
extern CFDictionaryRef IOReportCopyChannelsForDriver(io_service_t, CFAllocatorRef, CFErrorRef *);
extern CFStringRef IOReportChannelGetGroup(CFDictionaryRef);
extern CFStringRef IOReportChannelGetSubGroup(CFDictionaryRef);
extern uint8_t IOReportChannelGetFormat(CFDictionaryRef);
extern uint64_t IOReportChannelGetDriverID(CFDictionaryRef);

enum ReportFormat {
    FORMAT_UNKNOWN,
    FORMAT_SIMPLE,
    FORMAT_STATE,
    FORMAT_HISTOGRAM,
    FORMAT_SIMPLE_ARRAY,
    FORMAT_COUNT,
};

int main(void)
{
    io_iterator_t iterator = IO_OBJECT_NULL;
    IOReturn status = IOServiceGetMatchingServices(kIOMainPortDefault,
        IOServiceNameMatching("IO80211ReporterProxy"), &iterator);
    if (status != KERN_SUCCESS) {
        fputs("The WLAN reporter could not be enumerated.\n", stderr);
        return 1;
    }
    io_service_t proxy = IOIteratorNext(iterator);
    io_service_t extra = IOIteratorNext(iterator);
    IOObjectRelease(iterator);
    if (!proxy || extra) {
        if (proxy) IOObjectRelease(proxy);
        if (extra) IOObjectRelease(extra);
        fputs("Expected one WLAN reporter.\n", stderr);
        return 1;
    }
    uint64_t id = 0;
    status = IORegistryEntryGetRegistryEntryID(proxy, &id);
    if (status != KERN_SUCCESS) {
        IOObjectRelease(proxy);
        return 1;
    }
    CFDictionaryRef catalogue = IOReportCopyChannelsForDriver(proxy, NULL, NULL);
    IOObjectRelease(proxy);
    if (!catalogue || CFGetTypeID(catalogue) != CFDictionaryGetTypeID()) {
        if (catalogue) CFRelease(catalogue);
        fputs("The WLAN catalogue is unavailable.\n", stderr);
        return 1;
    }
    CFArrayRef rows = CFDictionaryGetValue(catalogue, CFSTR("IOReportChannels"));
    if (!rows || CFGetTypeID(rows) != CFArrayGetTypeID()) {
        CFRelease(catalogue);
        fputs("The catalogue lacks a channel array.\n", stderr);
        return 1;
    }
    struct {
        CFStringRef group;
        CFStringRef subgroup;
        const char *key;
        size_t matches;
        size_t formats[FORMAT_COUNT];
    } selected[] = {
        {CFSTR("Channel"), CFSTR("CCA Last Reported"), "cca_last_reported",0,{0}},
        {CFSTR("Channel"), CFSTR("CCA State"), "cca_state",0,{0}},
        {CFSTR("Interface en0"), CFSTR("Average CCA"), "en0_average",0,{0}},
        {CFSTR("Interface en0"), CFSTR("Average CCA State"), "en0_average_state",0,{0}},
        {CFSTR("Interface en0"), CFSTR("QBSS Values"), "en0_qbss_values",0,{0}},
        {CFSTR("Interface awdl0"), CFSTR("Average CCA"), "awdl_average",0,{0}},
    };
    const size_t n = sizeof(selected) / sizeof(selected[0]);
    CFIndex matches = 0;
    for (CFIndex i = 0; i < CFArrayGetCount(rows); ++i) {
        CFDictionaryRef row = CFArrayGetValueAtIndex(rows, i);
        if (CFGetTypeID(row) != CFDictionaryGetTypeID() || IOReportChannelGetDriverID(row) != id) continue;
        ++matches;
        CFStringRef group = IOReportChannelGetGroup(row);
        CFStringRef sub = IOReportChannelGetSubGroup(row);
        if (!group || !sub) continue;
        for (size_t p = 0; p < n; ++p) {
            if (!CFEqual(group, selected[p].group) || !CFEqual(sub, selected[p].subgroup)) continue;
            ++selected[p].matches;
            uint8_t format = IOReportChannelGetFormat(row);
            if (format >= FORMAT_COUNT) format = FORMAT_UNKNOWN;
            ++selected[p].formats[format];
        }
    }
    printf("{\"catalogue_available\":true,\"unprivileged\":%s,\"rows\":%ld,\"publisher_matched_rows\":%ld,\"groups\":{",
        (getuid() && geteuid()) ? "true" : "false", (long)CFArrayGetCount(rows), (long)matches);
    for (size_t p = 0; p < n; ++p) {
        printf("%s\"%s\":{\"matches\":%zu,\"simple\":%zu,\"state\":%zu,\"histogram\":%zu,\"simple_array\":%zu,\"other\":%zu}",
            p ? "," : "", selected[p].key, selected[p].matches,
            selected[p].formats[FORMAT_SIMPLE], selected[p].formats[FORMAT_STATE],
            selected[p].formats[FORMAT_HISTOGRAM], selected[p].formats[FORMAT_SIMPLE_ARRAY],
            selected[p].formats[FORMAT_UNKNOWN]);
    }
    puts("}}");
    CFRelease(catalogue);
    return 0;
}
