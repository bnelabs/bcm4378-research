/* Read interface timestamp capabilities and test two IPv4 loopback receive timestamps. */
#include <arpa/inet.h>
#include <net/if.h>
#include <netinet/in.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/sockio.h>
#include <sys/time.h>
#include <unistd.h>

static const char *json_bool(bool value)
{
    return value ? "true" : "false";
}

static bool check_loopback_timestamps(int socket_fd, bool *wall, bool *monotonic)
{
    const int enabled = 1;
    const struct timeval timeout = {.tv_sec = 1};
    if (setsockopt(socket_fd, SOL_SOCKET, SO_TIMESTAMP, &enabled, sizeof(enabled)) == -1 ||
        setsockopt(socket_fd, SOL_SOCKET, SO_TIMESTAMP_MONOTONIC, &enabled, sizeof(enabled)) == -1 ||
        setsockopt(socket_fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) == -1) {
        perror("setsockopt");
        return false;
    }

    struct sockaddr_in address = {
        .sin_len = sizeof(address),
        .sin_family = AF_INET,
        .sin_addr.s_addr = htonl(INADDR_LOOPBACK),
    };
    socklen_t address_length = sizeof(address);
    if (bind(socket_fd, (struct sockaddr *)&address, address_length) == -1 ||
        getsockname(socket_fd, (struct sockaddr *)&address, &address_length) == -1) {
        perror("loopback address");
        return false;
    }
    const char sent = 't';
    if (sendto(socket_fd, &sent, sizeof(sent), 0, (struct sockaddr *)&address, address_length) == -1) {
        perror("sendto loopback");
        return false;
    }

    char received = 0;
    struct iovec payload = {.iov_base = &received, .iov_len = sizeof(received)};
    union {
        struct cmsghdr alignment;
        unsigned char bytes[CMSG_SPACE(sizeof(struct timeval)) + CMSG_SPACE(sizeof(uint64_t))];
    } control = {0};
    struct msghdr message = {
        .msg_iov = &payload,
        .msg_iovlen = 1,
        .msg_control = control.bytes,
        .msg_controllen = sizeof(control.bytes),
    };
    ssize_t length = recvmsg(socket_fd, &message, 0);
    if (length == -1) {
        perror("recvmsg loopback");
        return false;
    }
    if (length != sizeof(received) || sent != received ||
        (message.msg_flags & (MSG_TRUNC | MSG_CTRUNC))) {
        fprintf(stderr, "Incomplete loopback datagram or ancillary data.\n");
        return false;
    }

    for (struct cmsghdr *header = CMSG_FIRSTHDR(&message); header != NULL;
         header = CMSG_NXTHDR(&message, header)) {
        if (header->cmsg_level != SOL_SOCKET)
            continue;
        if (header->cmsg_type == SCM_TIMESTAMP &&
            header->cmsg_len == CMSG_LEN(sizeof(struct timeval))) {
            struct timeval timestamp;
            memcpy(&timestamp, CMSG_DATA(header), sizeof(timestamp));
            *wall = timestamp.tv_sec > 0 && timestamp.tv_usec >= 0 && timestamp.tv_usec < 1000000;
        }
        if (header->cmsg_type == SCM_TIMESTAMP_MONOTONIC &&
            header->cmsg_len == CMSG_LEN(sizeof(uint64_t))) {
            uint64_t timestamp;
            memcpy(&timestamp, CMSG_DATA(header), sizeof(timestamp));
            *monotonic = timestamp != 0;
        }
    }
    return true;
}

int main(int argc, char **argv)
{
    if (argc != 2 || argv[1][0] == '\0' || strlen(argv[1]) >= IFNAMSIZ) {
        fprintf(stderr, "Usage: %s <interface>\n", argv[0]);
        return 2;
    }

    int socket_fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (socket_fd == -1) {
        perror("socket");
        return 1;
    }
    struct ifreq request = {0};
    strlcpy(request.ifr_name, argv[1], sizeof(request.ifr_name));
    if (ioctl(socket_fd, SIOCGIFCAP, &request) == -1) {
        perror("SIOCGIFCAP");
        close(socket_fd);
        return 1;
    }

    bool wall = false;
    bool monotonic = false;
    bool completed = check_loopback_timestamps(socket_fd, &wall, &monotonic);
    close(socket_fd);
    if (!completed)
        return 1;

    printf("{\"interface_supported_mask\":\"0x%x\",\"interface_enabled_mask\":\"0x%x\","
           "\"interface_hardware_timestamp_supported\":%s,"
           "\"interface_hardware_timestamp_enabled\":%s,"
           "\"interface_software_timestamp_supported\":%s,"
           "\"interface_software_timestamp_enabled\":%s,"
           "\"ipv4_loopback_wall_timestamp_received\":%s,"
           "\"ipv4_loopback_monotonic_timestamp_received\":%s}\n",
           (unsigned int)request.ifr_reqcap, (unsigned int)request.ifr_curcap,
           json_bool(request.ifr_reqcap & IFCAP_HW_TIMESTAMP),
           json_bool(request.ifr_curcap & IFCAP_HW_TIMESTAMP),
           json_bool(request.ifr_reqcap & IFCAP_SW_TIMESTAMP),
           json_bool(request.ifr_curcap & IFCAP_SW_TIMESTAMP),
           json_bool(wall), json_bool(monotonic));
    return 0;
}
