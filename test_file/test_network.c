#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>

int main(void) {
    int sockfd;
    struct sockaddr_in addr;

    printf("Network isolation test...\n");
    printf("Trying to connect to 8.8.8.8:53\n");

    sockfd = socket(AF_INET, SOCK_STREAM, 0);

    if (sockfd < 0) {
        perror("socket failed");
        return 1;
    }

    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(53);

    if (inet_pton(AF_INET, "8.8.8.8", &addr.sin_addr) <= 0) {
        perror("inet_pton failed");
        close(sockfd);
        return 1;
    }

    if (connect(sockfd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("connect failed");
        close(sockfd);
        return 1;
    }

    printf("Connection successful. Network is NOT isolated.\n");

    close(sockfd);
    return 0;
}