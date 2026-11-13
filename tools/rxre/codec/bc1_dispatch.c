#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>

static int has_avx2() {
    FILE* f=fopen("/proc/cpuinfo","r");
    if(!f) return 0;
    char line[4096];
    while(fgets(line,sizeof(line),f)){
        if(strstr(line,"flags")){
            if(strstr(line,"avx2")){ fclose(f); return 1; }
        }
    }
    fclose(f);
    return 0;
}

int main(int argc,char**argv){
    if(argc<6){ fprintf(stderr,"usage: %s e|d W H input output\n",argv[0]); return 1; }
    const char* scalar="/home/lucas/Escritorio/rxre/tools/rxre/codec/bc1_c_o2";
    const char* simd="/home/lucas/Escritorio/rxre/tools/rxre/codec/bc1_c_o3";
    const char* chosen = has_avx2() ? simd : scalar;
    /* exec chosen with same args */
    char** nargv=malloc((argc+1)*sizeof(char*));
    nargv[0]=chosen;
    for(int i=1;i<argc;i++) nargv[i]=argv[i];
    nargv[argc]=NULL;
    execv(chosen,nargv);
    perror("execv");
    return 1;
}
