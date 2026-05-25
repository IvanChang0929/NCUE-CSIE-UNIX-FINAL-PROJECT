#ifndef LOGGER_H
#define LOGGER_H

typedef enum {
    LOG_DEBUG,
    LOG_INFO,
    LOG_WARN,
    LOG_ERROR,
    LOG_SECURITY
} LogLevel;

int logger_init(const char *log_path);
void logger_close(void);

void logger_log(LogLevel level,
                const char *component,
                const char *fmt, ...);

const char *logger_level_to_string(LogLevel level);

#endif