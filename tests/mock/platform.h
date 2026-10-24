#ifndef TEST_DHD_PLATFORM_H
#define TEST_DHD_PLATFORM_H
#define AF_INET 2
#define SOCK_DGRAM 2
#define SOCK_CLOEXEC 02000000
#define IFNAMSIZ 16
#define SIOCDEVPRIVATE 0x89f0
struct ifreq { char ifr_name[16]; union { void *pointer; char reserved[24]; } data; };
#define ifr_data data.pointer
int mock_socket(int domain, int type, int protocol);
int mock_ioctl(int fd, unsigned long request, ...);
unsigned int mock_geteuid(void);
int mock_close(int fd);
#define socket mock_socket
#define ioctl mock_ioctl
#define geteuid mock_geteuid
#define close mock_close
#endif
