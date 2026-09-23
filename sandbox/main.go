package main

import (
 "context"
 "encoding/json"
 "io"
 "net/http"
 "os/exec"
 "path/filepath"
 "strings"
 "sync"
 "time"
)

type request struct { RepositoryPath string `json:"repository_path"`; Command []string `json:"command"`; TimeoutSeconds int `json:"timeout_seconds"` }
type capped struct { sync.Mutex; data []byte }
func (b *capped) Write(p []byte)(int,error){b.Lock();defer b.Unlock();n:=len(p);remaining:=(1<<20)-len(b.data);if remaining>0 {if len(p)>remaining {p=p[:remaining]};b.data=append(b.data,p...)};return n,nil}
func confined(path string)(string,error){root,err:=filepath.EvalSymlinks("/workspace");if err!=nil{return "",err};target,err:=filepath.EvalSymlinks(path);if err!=nil{return "",err};target,err=filepath.Abs(target);if err!=nil{return "",err};if !strings.HasPrefix(target,root+string(filepath.Separator)){return "",http.ErrNotSupported};return target,nil}
var slots=make(chan struct{},1)
func run(w http.ResponseWriter,r *http.Request){
 if r.Method!=http.MethodPost {http.Error(w,"POST required",405);return}
 select{case slots<-struct{}{}:defer func(){<-slots}();default:http.Error(w,"runner busy",429);return}
 var q request
 if json.NewDecoder(http.MaxBytesReader(w,r.Body,64<<10)).Decode(&q)!=nil||len(q.Command)==0 {http.Error(w,"invalid request",400);return}
 target,err:=confined(q.RepositoryPath);if err!=nil {http.Error(w,"path outside workspace or missing",403);return}
 if q.TimeoutSeconds<1||q.TimeoutSeconds>300 {q.TimeoutSeconds=120}
 ctx,cancel:=context.WithTimeout(r.Context(),time.Duration(q.TimeoutSeconds)*time.Second);defer cancel()
 cmd:=exec.CommandContext(ctx,q.Command[0],q.Command[1:]...);cmd.Dir=target;cmd.WaitDelay=time.Second
 output:=&capped{};cmd.Stdout=output;cmd.Stderr=output
 err=cmd.Run();status:="passed";if err!=nil {status="failed"}
 w.Header().Set("Content-Type","application/json")
 json.NewEncoder(w).Encode(map[string]any{"status":status,"output":string(output.data),"timed_out":ctx.Err()==context.DeadlineExceeded})
}
func main(){mux:=http.NewServeMux();mux.HandleFunc("/health",func(w http.ResponseWriter,_ *http.Request){io.WriteString(w,`{"status":"ok"}`)});mux.HandleFunc("/v1/runs",run);server:=http.Server{Addr:":8090",Handler:mux,ReadHeaderTimeout:5*time.Second};if err:=server.ListenAndServe();err!=nil {panic(err)}}
