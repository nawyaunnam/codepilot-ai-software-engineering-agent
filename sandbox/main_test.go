package main
import("testing";"net/http/httptest";"strings")
func TestOutputBound(t *testing.T){b:=&capped{};n,e:=b.Write([]byte(strings.Repeat("x",2<<20)));if e!=nil||n!=2<<20||len(b.data)!=1<<20 {t.Fatal("output not bounded")}}
func TestRejectGet(t *testing.T){w:=httptest.NewRecorder();run(w,httptest.NewRequest("GET","/v1/runs",nil));if w.Code!=405{t.Fatal(w.Code)}}
func TestRejectOutsideWorkspace(t *testing.T){w:=httptest.NewRecorder();run(w,httptest.NewRequest("POST","/v1/runs",strings.NewReader(`{"repository_path":"/etc","command":["true"]}`)));if w.Code!=403{t.Fatal(w.Code)}}
