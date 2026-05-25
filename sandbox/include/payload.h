#ifndef PAYLOAD_H
#define PAYLOAD_H

extern int stdout_pipe[2];
extern int stderr_pipe[2];

int compile_program(void);
void execute_program(void);

#endif 