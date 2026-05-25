#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <dirent.h>
#include <ctype.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <sys/mount.h>
#include <sys/wait.h>
#include <sys/time.h>
#include <sys/ptrace.h>
#include <arpa/inet.h>
#include <netinet/in.h>

void print_result(const char *id, const char *name, int pass, const char *detail) {
    printf("[%s] %s : %s\n", id, name, pass ? "PASS" : "FAIL");
    printf("     detail: %s\n\n", detail);
}

void test_host_file() {
    const char *paths[] = {
        "/home/ivanchang/NCUE-CSIE-UNIX-FINAL-PROJECT/backend/main.py",
        "/home/ivanchang/NCUE-CSIE-UNIX-FINAL-PROJECT/frontend/ui.py",
        "/root/.bashrc",
        NULL
    };

    int readable = 0;
    char detail[256] = "";

    for (int i = 0; paths[i] != NULL; i++) {
        int fd = open(paths[i], O_RDONLY);
        if (fd >= 0) {
            readable = 1;
            snprintf(detail, sizeof(detail), "可讀取主機檔案：%s", paths[i]);
            close(fd);
            break;
        }
    }

    if (!readable) {
        snprintf(detail, sizeof(detail), "無法讀取測試用主機路徑，隔離正常");
    }

    print_result("S-01", "讀取宿主機檔案", !readable, detail);
}

void test_shadow() {
    int fd = open("/etc/shadow", O_RDONLY);

    if (fd >= 0) {
        close(fd);
        print_result("S-02", "讀取 /etc/shadow", 0, "可以讀取 /etc/shadow，權限隔離失敗");
    } else {
        char detail[256];
        snprintf(detail, sizeof(detail), "open 失敗，errno=%d (%s)", errno, strerror(errno));
        print_result("S-02", "讀取 /etc/shadow", 1, detail);
    }
}

void test_network() {
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        char detail[256];
        snprintf(detail, sizeof(detail), "socket 建立失敗，errno=%d (%s)", errno, strerror(errno));
        print_result("S-03", "網路連線測試", 1, detail);
        return;
    }

    struct timeval timeout;
    timeout.tv_sec = 2;
    timeout.tv_usec = 0;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(80);
    inet_pton(AF_INET, "8.8.8.8", &addr.sin_addr);

    int ret = connect(sock, (struct sockaddr *)&addr, sizeof(addr));

    if (ret == 0) {
        close(sock);
        print_result("S-03", "網路連線測試", 0, "connect 8.8.8.8:80 成功，網路未被隔離");
    } else {
        char detail[256];
        snprintf(detail, sizeof(detail), "connect 失敗，errno=%d (%s)", errno, strerror(errno));
        close(sock);
        print_result("S-03", "網路連線測試", 1, detail);
    }
}

void test_proc() {
    DIR *dir = opendir("/proc");

    if (dir == NULL) {
        char detail[256];
        snprintf(detail, sizeof(detail), "無法開啟 /proc，errno=%d (%s)，視為未暴露主機 process", errno, strerror(errno));
        print_result("S-04", "/proc 檢查", 1, detail);
        return;
    }

    struct dirent *entry;
    int process_count = 0;

    while ((entry = readdir(dir)) != NULL) {
        int is_pid = 1;
        for (int i = 0; entry->d_name[i] != '\0'; i++) {
            if (!isdigit(entry->d_name[i])) {
                is_pid = 0;
                break;
            }
        }

        if (is_pid) {
            process_count++;
        }
    }

    closedir(dir);

    char detail[256];
    snprintf(detail, sizeof(detail), "/proc 中可見 PID 數量：%d", process_count);

    /*
       一般 sandbox 內只應看到少量 process。
       如果看到非常多 PID，可能代表暴露到宿主機 /proc。
    */
    print_result("S-04", "/proc 檢查", process_count <= 10, detail);
}

void test_uid_gid() {
    uid_t uid = getuid();
    gid_t gid = getgid();

    char detail[256];
    snprintf(detail, sizeof(detail), "uid=%d, gid=%d", uid, gid);

    print_result("S-05", "權限檢查", uid != 0 && gid != 0, detail);
}

void test_mount() {
    mkdir("/tmp/mount_test", 0755);

    int ret = mount("tmpfs", "/tmp/mount_test", "tmpfs", 0, "size=1m");

    if (ret == 0) {
        umount("/tmp/mount_test");
        print_result("S-06", "mount 測試", 0, "mount 成功，代表具備不應有的系統掛載權限");
    } else {
        char detail[256];
        snprintf(detail, sizeof(detail), "mount 失敗，errno=%d (%s)", errno, strerror(errno));
        print_result("S-06", "mount 測試", 1, detail);
    }
}

void test_dangerous_syscall() {
    pid_t pid = fork();

    if (pid < 0) {
        char detail[256];
        snprintf(detail, sizeof(detail), "fork 失敗，errno=%d (%s)，可能 fork 也被限制", errno, strerror(errno));
        print_result("S-07", "危險 syscall 測試", 1, detail);
        return;
    }

    if (pid == 0) {
        /*
           ptrace 常被視為危險 syscall。
           若 seccomp 有阻擋，子程序可能會被 SIGSYS 終止。
        */
        long ret = ptrace(PTRACE_TRACEME, 0, NULL, NULL);

        if (ret == -1) {
            _exit(100);
        }

        _exit(101);
    } else {
        int status;
        waitpid(pid, &status, 0);

        if (WIFSIGNALED(status)) {
            int sig = WTERMSIG(status);
            char detail[256];
            snprintf(detail, sizeof(detail), "子程序被 signal %d 終止，危險 syscall 可能已被阻擋", sig);
            print_result("S-07", "危險 syscall 測試", 1, detail);
        } else if (WIFEXITED(status)) {
            int code = WEXITSTATUS(status);

            if (code == 100) {
                print_result("S-07", "危險 syscall 測試", 1, "ptrace 執行失敗，代表受限制");
            } else {
                print_result("S-07", "危險 syscall 測試", 0, "ptrace 可能成功，seccomp 阻擋不足");
            }
        } else {
            print_result("S-07", "危險 syscall 測試", 1, "子程序未正常完成，視為受限制");
        }
    }
}

int main() {
    printf("========== Sandbox Isolation Test ==========\n\n");

    test_host_file();
    test_shadow();
    test_network();
    test_proc();
    test_uid_gid();
    test_mount();
    test_dangerous_syscall();

    printf("========== Test Finished ==========\n");

    return 0;
}