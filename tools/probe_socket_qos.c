#include <inttypes.h>
#include <netinet/in.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <unistd.h>

struct socket_kind {
    const char *family_name;
    const char *transport_name;
    int family;
    int type;
};

static bool
read_option(int fd, int option, void *value, socklen_t expected_size, const char *name)
{
    socklen_t size = expected_size;

    if (getsockopt(fd, SOL_SOCKET, option, value, &size) == -1) {
        perror(name);
        return false;
    }
    if (size != expected_size) {
        fprintf(stderr, "%s returned an unexpected value size\n", name);
        return false;
    }
    return true;
}

static bool
probe_service_types(int fd, const struct socket_kind *kind)
{
    const struct {
        const char *name;
        int value;
    } service_types[] = {
        {"BE", NET_SERVICE_TYPE_BE},
        {"BK", NET_SERVICE_TYPE_BK},
        {"SIG", NET_SERVICE_TYPE_SIG},
        {"VI", NET_SERVICE_TYPE_VI},
        {"VO", NET_SERVICE_TYPE_VO},
        {"RV", NET_SERVICE_TYPE_RV},
        {"AV", NET_SERVICE_TYPE_AV},
        {"OAM", NET_SERVICE_TYPE_OAM},
        {"RD", NET_SERVICE_TYPE_RD},
    };
    int initial;
    bool matched = true;

    if (!read_option(fd, SO_NET_SERVICE_TYPE, &initial, sizeof(initial), "SO_NET_SERVICE_TYPE")) {
        return false;
    }

    for (size_t i = 0; i < sizeof(service_types) / sizeof(service_types[0]); i++) {
        int requested = service_types[i].value;
        int observed;

        if (setsockopt(fd, SOL_SOCKET, SO_NET_SERVICE_TYPE, &requested, sizeof(requested)) == -1) {
            perror("SO_NET_SERVICE_TYPE");
            return false;
        }
        if (!read_option(fd, SO_NET_SERVICE_TYPE, &observed, sizeof(observed), "SO_NET_SERVICE_TYPE")) {
            return false;
        }
        printf("SO_NET_SERVICE_TYPE\t%s\t%s\t%s\t%d\t%d\t%d\n",
            kind->family_name, kind->transport_name, service_types[i].name, initial, requested, observed);
        matched = matched && requested == observed;
    }

    return matched;
}

static bool
probe_pacing_rate(int fd, const struct socket_kind *kind)
{
    const uint64_t requested = 125000;
    uint64_t initial, observed;

    if (!read_option(fd, SO_MAX_PACING_RATE, &initial, sizeof(initial), "SO_MAX_PACING_RATE")) {
        return false;
    }
    if (setsockopt(fd, SOL_SOCKET, SO_MAX_PACING_RATE, &requested, sizeof(requested)) == -1) {
        perror("SO_MAX_PACING_RATE");
        return false;
    }
    if (!read_option(fd, SO_MAX_PACING_RATE, &observed, sizeof(observed), "SO_MAX_PACING_RATE")) {
        return false;
    }
    printf("SO_MAX_PACING_RATE\t%s\t%s\tbytes/s\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\n",
        kind->family_name, kind->transport_name, initial, requested, observed);
    return requested == observed;
}

int
main(void)
{
    const struct socket_kind kinds[] = {
        {"IPv4", "TCP", AF_INET, SOCK_STREAM},
        {"IPv4", "UDP", AF_INET, SOCK_DGRAM},
        {"IPv6", "TCP", AF_INET6, SOCK_STREAM},
        {"IPv6", "UDP", AF_INET6, SOCK_DGRAM},
    };
    bool matched = true;

    // These sockets remain unbound and unconnected for the entire probe.
    puts("option\tfamily\ttransport\tvalue\tdefault\trequested\tobserved");
    for (size_t i = 0; i < sizeof(kinds) / sizeof(kinds[0]); i++) {
        int fd = socket(kinds[i].family, kinds[i].type, 0);
        if (fd == -1) {
            perror("socket");
            return EXIT_FAILURE;
        }
        bool service_types_ok = probe_service_types(fd, &kinds[i]);
        bool pacing_rate_ok = probe_pacing_rate(fd, &kinds[i]);
        close(fd);

        if (!service_types_ok || !pacing_rate_ok) {
            fprintf(stderr, "%s %s socket readback was incomplete or differed from the request\n",
                kinds[i].family_name, kinds[i].transport_name);
            matched = false;
        }
    }
    return matched ? EXIT_SUCCESS : EXIT_FAILURE;
}
