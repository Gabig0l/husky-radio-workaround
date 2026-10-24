/* SPDX-License-Identifier: MIT
 * Includes the production helper; only the OS-call boundary is mocked.
 * No sockets, driver ioctls or device access occur in this test executable.
 */
#include <assert.h>
#include <errno.h>
#include <inttypes.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define __linux__ 1
#define __aarch64__ 1
#define main helper_main
#include "../src/dhd_idle.c"
#undef main

static const char *scenario;
static int calls, sets, get_calls;
static int32_t current = 5;
static bool is(const char *s) { return strcmp(scenario, s) == 0; }
unsigned int mock_geteuid(void) { return is("nonroot") ? 1000U : 0U; }
int mock_socket(int domain, int type, int protocol) {
    assert(domain == AF_INET && type == (SOCK_DGRAM | SOCK_CLOEXEC) && protocol == 0);
    if (is("socket-fail")) { errno = EACCES; return -1; }
    return 42;
}
int mock_close(int fd) { assert(fd == 42); return 0; }
int mock_ioctl(int fd, unsigned long number, ...) {
    va_list args;
    va_start(args, number);
    struct ifreq *r = va_arg(args, struct ifreq *);
    va_end(args);
    struct dhd_ioctl_abi *c = r->ifr_data;
    assert(fd == 42 && number == SIOCDEVPRIVATE && strcmp(r->ifr_name, "wlan0") == 0);
    assert(c->driver == DHD_IOCTL_MAGIC && c->used == 0 && c->needed == 0);
    calls++;
    if (c->cmd == DHD_GET_MAGIC) {
        assert(calls == 1 && c->set == 0 && c->len == 4);
        if (is("magic-error")) { errno = EINVAL; return -1; }
        *(uint32_t *)c->buf = is("wrong-magic") ? 0U : DHD_IOCTL_MAGIC;
    } else if (c->cmd == DHD_GET_VERSION) {
        assert(calls == 2 && c->set == 0 && c->len == 4);
        if (is("version-error")) { errno = EINVAL; return -1; }
        *(uint32_t *)c->buf = is("wrong-version") ? 2U : 1U;
    } else if (c->cmd == DHD_GET_VAR) {
        get_calls++;
        assert(c->set == 0 && c->len == 256 && memcmp(c->buf, "idletime", 9) == 0);
        if (is("get-error") || (get_calls == 2 && is("readback-error"))) { errno = EINVAL; return -1; }
        if (!is("unchanged-buffer")) {
            int32_t value = is("negative") ? -1 : current;
            if (get_calls == 2 && is("readback-nonzero")) value = 5;
            memcpy(c->buf, &value, 4);
        }
    } else {
        assert(c->cmd == DHD_SET_VAR && calls == 4 && get_calls == 1 && sets == 0);
        assert(c->set == 1 && c->len == 13 && memcmp(c->buf, "idletime\0\0\0\0\0", 13) == 0);
        sets++;
        if (is("set-error")) { errno = EIO; return -1; }
        current = 0;
    }
    return 0;
}
int main(int argc, char **argv) {
    assert(argc == 2);
    scenario = argv[1];
    if (is("already-zero")) current = 0;
    char *set_args[] = {"test-helper", "explicit-set", "idletime", "0", NULL};
    char *inspect_args[] = {"test-helper", "inspect", NULL};
    char *invalid_args[] = {"test-helper", "explicit-set", "idletime", "5", NULL};
    int count = is("inspect") ? 2 : (is("default-inspect") ? 1 : 4);
    char **a = is("inspect") || is("default-inspect") ? inspect_args : (is("invalid-args") ? invalid_args : set_args);
    int result = helper_main(count, a);
    printf("TEST_RESULT rc=%d calls=%d gets=%d sets=%d\n", result, calls, get_calls, sets);
    return 0;
}
