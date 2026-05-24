#include <stdio.h>
#include <sys/stat.h>
#include <errno.h>
#include "result_writer.h"

static void escape_json(const char *src, char *dest){
    while(*src){
        if(*src == '"'){
            *dest++ = '\\'; *dest++ = '"';
        } else if(*src == '\\'){
            *dest++ = '\\'; *dest++ = '\\';
        } else if(*src == '\n'){
            *dest++ = '\\'; *dest++ = 'n';
        } else if(*src == '\r'){
            *dest++ = '\\'; *dest++ = 'r';
        } else if(*src == '\t'){
            *dest++ = '\\'; *dest++ = 't';
        } else {
            *dest++ = *src;
        }
        src++;
    }
    *dest = '\0';
}

void write_combined_json(const char *job_id, StageResult *comp, StageResult *exec){
    char result_dir[512], json_path[512];
    snprintf(result_dir, sizeof(result_dir), "./sandbox/result/job_%s", job_id);
    snprintf(json_path, sizeof(json_path), "%s/result.json", result_dir);

    mkdir("./sandbox/result", 0777);
    if(mkdir(result_dir, 0777) == -1 && errno != EEXIST){
        perror("mkdir result_dir");
        return;
    }

   
    if(exec->executed) {
        char txt_path[512];
        snprintf(txt_path, sizeof(txt_path), "%s/output.txt", result_dir);

        FILE *ftxt = fopen(txt_path, "r");
        if(ftxt != NULL) {
            // 讀取實體檔案內容，蓋掉原本 Pipe 抓到的空資料
            // sizeof(exec->stdout_buf) - 1 確保不會 Buffer Overflow
            size_t read_bytes = fread(exec->stdout_buf, 1, sizeof(exec->stdout_buf) - 1, ftxt);
            exec->stdout_buf[read_bytes] = '\0'; // 確保字串安全結尾
            fclose(ftxt);
        } else {
            exec->stdout_buf[0] = '\0';
        }
    }

    FILE *fjson = fopen(json_path, "w");
    if(fjson == NULL){
        perror("fopen json_path");
        return;
    }

    char esc_out[8192] = {0};
    char esc_err[8192] = {0};

    fprintf(fjson, "{\n");

    if(comp->executed){
        escape_json(comp->stdout_buf, esc_out);
        escape_json(comp->stderr_buf, esc_err);
        fprintf(fjson, "  \"compile\": {\n");
        fprintf(fjson, "    \"exit_code\": %d,\n", comp->exit_code);
        fprintf(fjson, "    \"stdout\": \"%s\",\n", esc_out);
        fprintf(fjson, "    \"stderr\": \"%s\"\n", esc_err);
        fprintf(fjson, "  }%s\n", exec->executed ? "," : "");
    }

    if(exec->executed){
        escape_json(exec->stdout_buf, esc_out);
        escape_json(exec->stderr_buf, esc_err);
        fprintf(fjson, "  \"execute\": {\n");
        fprintf(fjson, "    \"exit_code\": %d,\n", exec->exit_code);
        fprintf(fjson, "    \"stdout\": \"%s\",\n", esc_out);
        fprintf(fjson, "    \"stderr\": \"%s\"\n", esc_err);
        fprintf(fjson, "  }\n");
    }

    fprintf(fjson, "}\n");
    fclose(fjson);
    
    fprintf(stderr, "[Parent] Combined JSON saved to %s\n", json_path);
}