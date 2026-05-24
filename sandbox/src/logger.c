#include "logger.h"

#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <time.h>
#include <errno.h>
#include <sys/stat.h>

#define LOG_BUFFER_SIZE 2048
#define TIME_BUFFER_SIZE 64

static FILE *log_file = NULL;

static void get_timestamp(char *buffer, size_t size)
{
    time_t now = time(NULL);
    struct tm tm_info;

    localtime_r(&now, &tm_info);
    strftime(buffer, size, "%Y-%m-%d %H:%M:%S", &tm_info);
}

static int ensure_parent_dir(const char *path)
{
    char tmp[512];
    char *slash;

    if (path == NULL) {
        return -1;
    }

    strncpy(tmp, path, sizeof(tmp) - 1);
    tmp[sizeof(tmp) - 1] = '\0';

    slash = strrchr(tmp, '/');
    if (slash == NULL) {
        return 0;
    }

    *slash = '\0';

    if (strlen(tmp) == 0) {
        return 0;
    }

    if (mkdir(tmp, 0755) == -1 && errno != EEXIST) {
        return -1;
    }

    return 0;
}

const char *logger_level_to_string(LogLevel level)
{
    switch (level) {
        case LOG_DEBUG:
            return "DEBUG";
        case LOG_INFO:
            return "INFO";
        case LOG_WARN:
            return "WARN";
        case LOG_ERROR:
            return "ERROR";
        case LOG_SECURITY:
            return "SECURITY";
        default:
            return "UNKNOWN";
    }
}

int logger_init(const char *log_path)
{
    if (log_path == NULL) {
        log_path = "../logs/sandbox.log";
    }

    if (ensure_parent_dir(log_path) == -1) {
        fprintf(stderr, "logger: failed to create log directory: %s\n", strerror(errno));
        return -1;
    }

    log_file = fopen(log_path, "a");
    if (log_file == NULL) {
        fprintf(stderr, "logger: failed to open log file %s: %s\n",
                log_path,
                strerror(errno));
        return -1;
    }

    setvbuf(log_file, NULL, _IOLBF, 0);

    logger_log(LOG_INFO, "LOGGER", "Logger initialized: file=%s", log_path);

    return 0;
}

void logger_close(void)
{
    if (log_file != NULL) {
        logger_log(LOG_INFO, "LOGGER", "Logger closed");
        fclose(log_file);
        log_file = NULL;
    }
}

void logger_log(LogLevel level,
                const char *component,
                const char *fmt, ...)
{
    char timestamp[TIME_BUFFER_SIZE];
    char message[LOG_BUFFER_SIZE];

    va_list args;

    if (log_file == NULL) {
        return;
    }

    get_timestamp(timestamp, sizeof(timestamp));

    va_start(args, fmt);
    vsnprintf(message, sizeof(message), fmt, args);
    va_end(args);

    fprintf(log_file,
            "[%s] [%s] [%s] %s\n",
            timestamp,
            logger_level_to_string(level),
            component ? component : "UNKNOWN",
            message);

    fflush(log_file);
}


/*
logger_log(LOG_INFO, "SANDBOX", "Sandbox started");

    logger_log(LOG_INFO, "NAMESPACE", "Creating namespaces");
    logger_log(LOG_INFO, "LIMIT", "Setting resource limits");
    logger_log(LOG_SECURITY, "SECCOMP", "Installing seccomp filter");

    logger_log(LOG_INFO, "RESULT", "Execution finished: exit_code=%d", 0);

*/