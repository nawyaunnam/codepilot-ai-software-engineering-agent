package main

import (
 "archive/zip"
 "bytes"
 "context"
 "crypto/subtle"
 "encoding/base64"
 "encoding/json"
 "errors"
 "fmt"
 "io"
 "net/http"
 "os"
 "os/exec"
 "path/filepath"
 "strings"
 "sync"
 "time"
)

type request struct {Archive string `json:"archive"`;Command []string `json:"command"`;TimeoutSeconds int `json:"timeout_seconds"`}
type capped struct {sync.Mutex;data []byte}
func(b *capped)Write(p []byte)(int,error){b.Lock();defer b.Unlock();n:=len(p);remaining:=(1<<20)-len(b.data);if remaining>0{if len(p)>remaining{p=p[:remaining]};b.data=append(b.data,p...)};return n,nil}
var slots=make(chan struct{},2)
func unpack(data []byte,root string)error{
 z,err:=zip.NewReader(bytes.NewReader(data),int64(len(data)));if err!=nil{return err};if len(z.File)>10000{return errors.New("too many files")}
 var total uint64;seen:=map[string]bool{}
 for _,f:=range z.File{
  name:=f.Name
  if name==""||filepath.IsAbs(name)||strings.Contains(name,"\\")||strings.Contains(name,":")||f.Mode()&os.ModeSymlink!=0{return errors.New("unsafe ZIP path")}
  for _,part:=range strings.Split(name,"/"){if part==".."||part==".git"{return errors.New("unsafe ZIP path")}}
  if seen[name]{return errors.New("duplicate ZIP path")};seen[name]=true
  total+=f.UncompressedSize64;if total>50_000_000||f.UncompressedSize64>2_000_000{return errors.New("expanded archive too large")}
  dest:=filepath.Join(root,name);if f.FileInfo().IsDir(){continue};if err=os.MkdirAll(filepath.Dir(dest),0755);err!=nil{return err}
  src,e:=f.Open();if e!=nil{return e};content,e:=io.ReadAll(io.LimitReader(src,2_000_001));src.Close();if e!=nil||len(content)>2_000_000{return errors.New("invalid ZIP entry")}
  if err=os.WriteFile(dest,content,0644);err!=nil{return err}
 };return nil
}
func docker(ctx context.Context,args ...string)([]byte,error){cmd:=exec.CommandContext(ctx,"docker",args...);cmd.WaitDelay=time.Second;output:=&capped{};cmd.Stdout=output;cmd.Stderr=output;err:=cmd.Run();return output.data,err}
func cleanup(id string){ctx,cancel:=context.WithTimeout(context.Background(),10*time.Second);defer cancel();docker(ctx,"rm","-f",id)}
func execute(ctx context.Context,root string,command []string)(map[string]any,error){
 if len(command)==0||len(command)>20{return nil,errors.New("command required")}
 image:=os.Getenv("TEST_IMAGE");if image==""{image="codepilot-test-runtime:local"}
 // Only this broker has the Docker socket. Child containers never inherit mounts or credentials.
 args:=[]string{"create","--pull=never","--network=none","--read-only","--cap-drop=ALL","--security-opt=no-new-privileges","--pids-limit=128","--memory=512m","--cpus=1","--user=65534:65534","--tmpfs=/tmp:rw,nosuid,size=256m,mode=1777",image,"sh","-c",`cp -R /source /tmp/work && cd /tmp/work && exec "$@"`,"runner"}
 args=append(args,command...)
 out,err:=docker(ctx,args...);if err!=nil{return nil,fmt.Errorf("container creation failed: %s",out)}
 id:=strings.TrimSpace(string(out));defer cleanup(id)
 if _,err=docker(ctx,"cp",root+"/.",id+":/source");err!=nil{return nil,errors.New("snapshot copy failed")}
 output,startErr:=docker(ctx,"start","-a",id)
 if ctx.Err()!=nil{return map[string]any{"status":"timed_out","output":string(output),"timed_out":true},nil}
 inspected,err:=docker(ctx,"inspect","--format={{.State.ExitCode}}",id);if err!=nil{return nil,errors.New("container status unavailable")}
 status:="passed";if startErr!=nil||strings.TrimSpace(string(inspected))!="0"{status="failed"}
 return map[string]any{"status":status,"exit_code":strings.TrimSpace(string(inspected)),"output":string(output),"timed_out":false},nil
}
func run(w http.ResponseWriter,r *http.Request){
 if r.Method!=http.MethodPost{http.Error(w,"POST required",405);return}
 token:=os.Getenv("SANDBOX_TOKEN");if len(token)<32||subtle.ConstantTimeCompare([]byte(r.Header.Get("Authorization")),[]byte("Bearer "+token))!=1{http.Error(w,"unauthorized",401);return}
 select{case slots<-struct{}{}:defer func(){<-slots}();default:http.Error(w,"runner busy",429);return}
 var q request;if json.NewDecoder(http.MaxBytesReader(w,r.Body,70_000_000)).Decode(&q)!=nil{http.Error(w,"invalid request",400);return}
 if q.TimeoutSeconds<1||q.TimeoutSeconds>300{http.Error(w,"timeout must be 1-300 seconds",400);return}
 archive,err:=base64.StdEncoding.DecodeString(q.Archive);if err!=nil||len(archive)>50_000_000{http.Error(w,"invalid archive",400);return}
 root,err:=os.MkdirTemp("","codepilot-run-");if err!=nil{http.Error(w,"workspace unavailable",503);return};defer os.RemoveAll(root);os.Chmod(root,0755)
 if err=unpack(archive,root);err!=nil{http.Error(w,err.Error(),400);return}
 ctx,cancel:=context.WithTimeout(r.Context(),time.Duration(q.TimeoutSeconds)*time.Second);defer cancel()
 result,err:=execute(ctx,root,q.Command);if err!=nil{http.Error(w,err.Error(),503);return}
 w.Header().Set("Content-Type","application/json");json.NewEncoder(w).Encode(result)
}
func main(){mux:=http.NewServeMux();mux.HandleFunc("/health",func(w http.ResponseWriter,_ *http.Request){io.WriteString(w,`{"status":"ok"}`)});mux.HandleFunc("/v1/runs",run);server:=http.Server{Addr:":8090",Handler:mux,ReadHeaderTimeout:5*time.Second};if err:=server.ListenAndServe();err!=nil{panic(err)}}
