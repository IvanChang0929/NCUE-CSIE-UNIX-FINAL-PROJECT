#include <stdio.h>
#include <sys/stat.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include "result_writer.h"
#include "../../logger/logger.h"

/*
 * 直接把 JSON string 寫到 FILE。
 *
 * 原本的 escape_json 只處理了 ", \, \n, \r, \t，
 * 但使用者程式可能印出其他 control character，例如 ESC(\x1b)、\b、\f、\x01。
 * 這些字元如果直接出現在 JSON 字串內，Python json.load() 會噴：
 *   JSONDecodeError: Invalid control character
 *
 * 所以這裡統一把 0x00 ~ 0x1F 都轉成合法 JSON escape。
 */
static void json_write_string(FILE *fp, const char *s) {
    fputc('"', fp);

    if (s == NULL) {
        fputc('"', fp);
        return;
    }

    const unsigned char *p = (const unsigned char *)s;

    while (*p) {
        switch (*p) {
            case '\"':
                fputs("\\\"", fp);
                break;

            case '\\':
                fputs("\\\\", fp);
                break;

            case '\b':
                fputs("\\b", fp);
                break;

            case '\f':
                fputs("\\f", fp);
                break;

            case '\n':
                fputs("\\n", fp);
                break;

            case '\r':
                fputs("\\r", fp);
                break;

            case '\t':
                fputs("\\t", fp);
                break;

            default:
                if (*p < 0x20) {
                    fprintf(fp, "\\u%04x", *p);
                } else {
                    fputc(*p, fp);
                }
                break;
        }

        p++;
    }

    fputc('"', fp);
}


static void json_write_key_string(FILE *fp, const char *key, const char *value, int comma) {
    fprintf(fp, "    \"%s\": ", key);
    json_write_string(fp, value);
    fprintf(fp, "%s\n", comma ? "," : "");
}


static void json_write_status_message(FILE *fp, StageResult *stage, const char *success_msg, const char *fail_msg) {
    const char *msg = NULL;

    if (stage->status_message[0] != '\0') {
        msg = stage->status_message;
    } else if (stage->exit_code == 0) {
        msg = success_msg;
    } else {
        msg = fail_msg;
    }

    json_write_key_string(fp, "status_message", msg, 1);
}


void write_combined_json(const char *job_id, StageResult *comp, StageResult *exec) {
    char result_dir[512], json_path[512];

    snprintf(result_dir, sizeof(result_dir), "./sandbox/result/job_%s", job_id);
    snprintf(json_path, sizeof(json_path), "%s/result.json", result_dir);

    mkdir("./sandbox/result", 0777);

    if (mkdir(result_dir, 0777) == -1 && errno != EEXIST) {
        perror("mkdir result_dir");
        return;
    }

    /*
     * 如果 execute stage 有把 stdout 另外寫到 output.txt，
     * 在輸出 JSON 前讀回來。
     */
    if (exec != NULL && exec->executed) {
        char txt_path[512];
        snprintf(txt_path, sizeof(txt_path), "%s/output.txt", result_dir);

        FILE *ftxt = fopen(txt_path, "r");

        if (ftxt != NULL) {
            size_t read_bytes = fread(exec->stdout_buf, 1, sizeof(exec->stdout_buf) - 1, ftxt);
            exec->stdout_buf[read_bytes] = '\0';
            fclose(ftxt);
        } else {
            exec->stdout_buf[0] = '\0';
        }
    }

    FILE *fjson = fopen(json_path, "w");

    if (fjson == NULL) {
        perror("fopen json_path");
        return;
    }

    fprintf(fjson, "{\n");

    if (comp != NULL && comp->executed) {
        fprintf(fjson, "  \"compile\": {\n");
        fprintf(fjson, "    \"exit_code\": %d,\n", comp->exit_code);

        json_write_status_message(fjson, comp, "Success", "Compile Error");
        json_write_key_string(fjson, "stdout", comp->stdout_buf, 1);
        json_write_key_string(fjson, "stderr", comp->stderr_buf, 0);

        fprintf(fjson, "  }%s\n", (exec != NULL && exec->executed) ? "," : "");
    }

    if (exec != NULL && exec->executed) {
        fprintf(fjson, "  \"execute\": {\n");
        fprintf(fjson, "    \"exit_code\": %d,\n", exec->exit_code);

        json_write_status_message(fjson, exec, "Normal Exit", "Runtime Error");
        json_write_key_string(fjson, "stdout", exec->stdout_buf, 1);
        json_write_key_string(fjson, "stderr", exec->stderr_buf, 1);

        fprintf(fjson, "    \"time_ms\": %ld,\n", exec->time_ms);
        fprintf(fjson, "    \"memory_kb\": %ld\n", exec->memory_kb);

        fprintf(fjson, "  }\n");
    }

    fprintf(fjson, "}\n");

    /*
     * 確保 worker 讀取前，內容已經完整寫入。
     */
    fflush(fjson);
    fclose(fjson);

    fprintf(stderr, "[Parent][Job %s] Combined JSON saved to %s\n", job_id, json_path);
    logger_log(LOG_INFO, "result_writer", "Combined JSON saved to %s. Job ID: %s", json_path, job_id);
}
