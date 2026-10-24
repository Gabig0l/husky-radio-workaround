/* SPDX-License-Identifier: MIT */
/* Minimal local DHD idletime helper. No interface selection or general iovars.
 * Source/ABI evidence and build limitations are recorded in README.md.
 * Only `explicit-set idletime 0` can issue DHD_SET_VAR.
 */
#define _DEFAULT_SOURCE 1
#include <errno.h>
#include <inttypes.h>
#include <linux/sockios.h>
#include <net/if.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>

#if !defined(__linux__) || !defined(__aarch64__)
#error "Build only for the Linux AArch64 kernel ABI."
#endif
#if __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "The audited Pixel ABI is little endian."
#endif

enum {
    DHD_GET_MAGIC = 0,
    DHD_GET_VERSION = 1,
    DHD_GET_VAR = 2,
    DHD_SET_VAR = 3,
    DHD_IOCTL_VERSION = 1,
    DHD_SMALL_BUFFER = 256,
};
#define DHD_IOCTL_MAGIC UINT32_C(0x00444944)

/* Default natural packing, as in the official DHD userspace header. */
struct dhd_ioctl_abi {
    uint32_t cmd;
    void *buf;
    uint32_t len;
    uint32_t set;
    uint32_t used;
    uint32_t needed;
    uint32_t driver;
};

_Static_assert(sizeof(void *) == 8, "64-bit pointers required");
_Static_assert(sizeof(((struct dhd_ioctl_abi *)0)->set) == 4, "DHD set is uint32");
_Static_assert(offsetof(struct dhd_ioctl_abi, cmd) == 0, "DHD cmd offset");
_Static_assert(offsetof(struct dhd_ioctl_abi, buf) == 8, "DHD buf offset");
_Static_assert(offsetof(struct dhd_ioctl_abi, len) == 16, "DHD len offset");
_Static_assert(offsetof(struct dhd_ioctl_abi, set) == 20, "DHD set offset");
_Static_assert(offsetof(struct dhd_ioctl_abi, used) == 24, "DHD used offset");
_Static_assert(offsetof(struct dhd_ioctl_abi, needed) == 28, "DHD needed offset");
_Static_assert(offsetof(struct dhd_ioctl_abi, driver) == 32, "DHD driver offset");
_Static_assert(sizeof(struct dhd_ioctl_abi) == 40, "DHD structure size");
_Static_assert(IFNAMSIZ == 16, "Linux interface name length");
_Static_assert(offsetof(struct ifreq, ifr_data) == 16, "ifreq pointer offset");
_Static_assert(sizeof(struct ifreq) == 40, "ifreq structure size");
_Static_assert(SIOCDEVPRIVATE == 0x89f0, "Audited private ioctl number");

static int issue(int fd, uint32_t command, void *buffer, uint32_t length,
                 bool set, bool allow_write, const char *operation)
{
    struct dhd_ioctl_abi control;
    struct ifreq request;
    int result, saved_errno;

    if (command > DHD_SET_VAR ||
        (command == DHD_SET_VAR && (!allow_write || !set)) ||
        (command != DHD_SET_VAR && set)) {
        fprintf(stderr, "Refused unexpected ioctl operation.\n");
        return -1;
    }
    memset(&control, 0, sizeof(control));
    memset(&request, 0, sizeof(request));
    control.cmd = command;
    control.buf = buffer;
    control.len = length;
    control.set = set;
    control.driver = DHD_IOCTL_MAGIC;
    memcpy(request.ifr_name, "wlan0", sizeof("wlan0"));
    request.ifr_data = (void *)&control;
    errno = 0;
    result = ioctl(fd, SIOCDEVPRIVATE, &request);
    saved_errno = errno;
    if (result != 0) {
        fprintf(stderr, "%s failed: ioctl_return=%d errno=%d (%s).\n",
                operation, result, saved_errno, strerror(saved_errno));
        return -1;
    }
    return 0;
}

static int verify_driver(int fd)
{
    uint32_t magic = 0, version = 0;
    if (issue(fd, DHD_GET_MAGIC, &magic, sizeof(magic), false, false,
              "DHD_GET_MAGIC") != 0)
        return -1;
    printf("interface=wlan0 magic=0x%08" PRIx32 "\n", magic);
    if (magic != DHD_IOCTL_MAGIC) {
        fprintf(stderr, "Driver magic mismatch; stopping.\n");
        return -1;
    }
    if (issue(fd, DHD_GET_VERSION, &version, sizeof(version), false, false,
              "DHD_GET_VERSION") != 0)
        return -1;
    printf("ioctl_version=%" PRIu32 "\n", version);
    if (version != DHD_IOCTL_VERSION) {
        fprintf(stderr, "Driver ioctl version mismatch; stopping.\n");
        return -1;
    }
    return 0;
}

static int get_idletime(int fd, int32_t *value, const char *operation)
{
    unsigned char buffer[DHD_SMALL_BUFFER];
    int32_t unchanged;
    memset(buffer, 0, sizeof(buffer));
    memcpy(buffer, "idletime", sizeof("idletime"));
    memcpy(&unchanged, buffer, sizeof(unchanged));
    if (issue(fd, DHD_GET_VAR, buffer, sizeof(buffer), false, false,
              operation) != 0)
        return -1;
    memcpy(value, buffer, sizeof(*value));
    if (*value < 0 || *value == unchanged) {
        fprintf(stderr, "%s returned an invalid or unchanged result; stopping.\n",
                operation);
        return -1;
    }
    return 0;
}

static int set_idletime_zero(int fd)
{
    unsigned char buffer[sizeof("idletime") + sizeof(int32_t)];
    memset(buffer, 0, sizeof(buffer));
    memcpy(buffer, "idletime", sizeof("idletime"));
    /* Four zero bytes follow the terminating NUL. */
    return issue(fd, DHD_SET_VAR, buffer, sizeof(buffer), true, true,
                 "DHD_SET_VAR idletime=0");
}

static void usage(const char *program)
{
    fprintf(stderr, "Usage: %s inspect\n"
                    "       %s explicit-set idletime 0\n", program, program);
}

int main(int argc, char **argv)
{
    bool do_set;
    int fd, result = 1;
    int32_t before = -1, after = -1;

    if (argc == 1 || (argc == 2 && strcmp(argv[1], "inspect") == 0)) {
        do_set = false;
    } else if (argc == 4 && strcmp(argv[1], "explicit-set") == 0 &&
               strcmp(argv[2], "idletime") == 0 && strcmp(argv[3], "0") == 0) {
        do_set = true;
    } else {
        usage(argv[0]);
        return 2;
    }
    /* CAP_NET_ADMIN is checked by the kernel; never try to gain it here. */
    if (geteuid() != 0) {
        fprintf(stderr, "Run this helper in an already authorized root context.\n");
        return 1;
    }
    fd = socket(AF_INET, SOCK_DGRAM | SOCK_CLOEXEC, 0);
    if (fd < 0) {
        fprintf(stderr, "socket failed: errno=%d (%s).\n", errno, strerror(errno));
        return 1;
    }
    if (verify_driver(fd) != 0 ||
        get_idletime(fd, &before, "DHD_GET_VAR idletime") != 0)
        goto done;
    printf("idletime_before=%" PRId32 "\n", before);
    fflush(stdout);
    if (!do_set) {
        printf("mode=inspect mutation=none\n");
        result = 0;
        goto done;
    }
    if (before == 0) {
        printf("mode=explicit-set idletime=0 already_zero=1 mutation=none\n");
        result = 0;
        goto done;
    }
    if (set_idletime_zero(fd) != 0) {
        fprintf(stderr, "SET failed; current idletime is unconfirmed. No retry.\n");
        result = 3;
        goto done;
    }
    if (get_idletime(fd, &after, "DHD_GET_VAR idletime verify") != 0) {
        fprintf(stderr, "SET returned success, but verification failed. No retry.\n");
        result = 4;
        goto done;
    }
    printf("idletime_after=%" PRId32 "\n", after);
    if (after != 0) {
        fprintf(stderr, "Readback differs from zero; do not assume runtime PM is disabled.\n");
        result = 4;
        goto done;
    }
    printf("mode=explicit-set verified_idletime=0\n");
    result = 0;
done:
    close(fd);
    return result;
}
