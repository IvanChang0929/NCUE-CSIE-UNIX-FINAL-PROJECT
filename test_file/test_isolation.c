#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <dirent.h>
#include <ctype.h>
#include <sys/types.h>

void print_result(const char *id, const char *name, int pass, const char *detail) {
    printf("[%s] %s : %s\n", id, name, pass ? "PASS" : "FAIL");
    printf("     detail: %s\n\n", detail);
}

void test_host_file() {
    const char *paths[] = {
        "/home/ivanchang/NCUE-CSIE-UNIX-FINAL-PROJECT/backend/main.py",
        "/home/ivanchang/NCUE-CSIE-UNIX-FINAL-PROJECT/frontend/ui.py",
        "/home/ivanchang/NCUE-CSIE-UNIX-FINAL-PROJECT/sandbox/worker.py",
        "/root/.bashrc",
        NULL
    };

    int readable = 0;
    char detail[512] = "";

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
        snprintf(detail, sizeof(detail), "無法讀取指定的宿主機路徑，隔離正常");
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

void test_proc() {
    DIR *dir = opendir("/proc");

    if (dir == NULL) {
        char detail[256];
        snprintf(detail, sizeof(detail), "無法開啟 /proc，errno=%d (%s)", errno, strerror(errno));
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
       sandbox 裡通常只會看到少量 process。
       如果看到非常多 PID，代表可能看到宿主機 process。
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

int main() {
    printf("========== Sandbox Isolation Safe Test ==========\n\n");

    test_host_file();
    test_shadow();
    test_proc();
    test_uid_gid();

    printf("========== Safe Test Finished ==========\n");

    return 0;
}