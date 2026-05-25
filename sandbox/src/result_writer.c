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
            size_t read_bytes = fread(exec->stdout_buf, 1, sizeof(exec->stdout_buf) - 1, ftxt);
            exec->stdout_buf[read_bytes] = '\0'; 
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

    char *esc_out = (char *)malloc(65536);
    char *esc_err = (char *)malloc(65536);
    
    if (esc_out == NULL || esc_err == NULL) {
        perror("malloc failed in write_combined_json");
        if (esc_out) free(esc_out);
        if (esc_err) free(esc_err);
        fclose(fjson);
        return;
    }

    fprintf(fjson, "{\n");

    if(comp->executed){
        escape_json(comp->stdout_buf, esc_out);
        escape_json(comp->stderr_buf, esc_err);
        fprintf(fjson, "  \"compile\": {\n");
        fprintf(fjson, "    \"exit_code\": %d,\n", comp->exit_code);
        
        if (comp->status_message[0] != '\0') {
            fprintf(fjson, "    \"status_message\": \"%s\",\n", comp->status_message);
        } else {
            if (comp->exit_code == 0) {
                fprintf(fjson, "    \"status_message\": \"Success\",\n");
            } else {
                fprintf(fjson, "    \"status_message\": \"Compile Error\",\n");
            }
        }
        
        fprintf(fjson, "    \"stdout\": \"%s\",\n", esc_out);
        fprintf(fjson, "    \"stderr\": \"%s\"\n", esc_err);
        fprintf(fjson, "  }%s\n", exec->executed ? "," : "");
    }

    if(exec->executed){
        escape_json(exec->stdout_buf, esc_out);
        escape_json(exec->stderr_buf, esc_err);
        fprintf(fjson, "  \"execute\": {\n");
        fprintf(fjson, "    \"exit_code\": %d,\n", exec->exit_code);
        
        if (exec->status_message[0] != '\0') {
            fprintf(fjson, "    \"status_message\": \"%s\",\n", exec->status_message);
        } else {
            fprintf(fjson, "    \"status_message\": \"Normal Exit\",\n");
        }
        fprintf(fjson, "    \"stdout\": \"%s\",\n", esc_out);
        fprintf(fjson, "    \"stderr\": \"%s\",\n", esc_err);
        fprintf(fjson, "    \"time_ms\": %ld,\n", exec->time_ms);
        fprintf(fjson, "    \"memory_kb\": %ld\n", exec->memory_kb);
        fprintf(fjson, "  }\n");
    }
    fprintf(fjson, "}\n");
    
    //強制把 Buffer 刷新進硬碟並關閉
    fflush(fjson);
    fclose(fjson);
    
    //關鍵修正：記得釋放記憶體避免 Memory Leak
    free(esc_out);
    free(esc_err);
    
    //如果是獨立 Process 跑這句話沒事，但建議帶上 job_id 方便在混亂的 Log 中識別
    fprintf(stderr, "[Parent][Job %s] Combined JSON saved to %s\n", job_id, json_path);
}