#include <stdio.h>
#include <dirent.h>
#include <ctype.h>
#include <string.h>

int is_number(const char *s) {
    for (int i = 0; s[i]; i++) {
        if (!isdigit((unsigned char)s[i])) {
            return 0;
        }
    }
    return 1;
}

int main() {
    DIR *dir;
    struct dirent *entry;
    int count = 0;

    printf("/proc process visibility test\n");

    dir = opendir("/proc");
    if (dir == NULL) {
        perror("opendir /proc");
        return 1;
    }

    printf("Visible PIDs:\n");

    while ((entry = readdir(dir)) != NULL) {
        if (is_number(entry->d_name)) {
            printf("PID: %s\n", entry->d_name);
            count++;
        }
    }

    closedir(dir);

    printf("Total visible process count: %d\n", count);

    if (count <= 5) {
        printf("[OK] /proc only shows sandbox-local processes.\n");
    } else {
        printf("[WARN] too many processes visible. Check PID namespace or /proc mount.\n");
    }

    return 0;
}