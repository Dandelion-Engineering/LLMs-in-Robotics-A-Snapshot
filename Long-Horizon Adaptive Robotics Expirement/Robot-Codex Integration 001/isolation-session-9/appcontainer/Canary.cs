// Synthetic non-model canary. Reads only task-created files and sends no secrets.
using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Threading;

class Canary {
    [DllImport("advapi32.dll", SetLastError=true)] static extern bool OpenProcessToken(IntPtr p, uint a, out IntPtr t);
    [DllImport("advapi32.dll", SetLastError=true)] static extern bool GetTokenInformation(IntPtr t, int c, out uint v, uint n, out uint r);
    [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
    static string log;
    static void Record(string name, string result) { File.AppendAllText(log, name + "\t" + result.Replace("\r", " ").Replace("\n", " ") + "\n"); }
    static string Failure(Exception e) { return e.GetType().Name + ":" + (e.HResult & 65535) + ":" + e.Message; }
    static void Read(string name, string path) {
        try { Record(name, "READ:" + File.ReadAllText(path)); } catch (Exception e) { Record(name, Failure(e)); }
    }
    static void Write(string name, string path) {
        try { File.WriteAllText(path, "SYNTHETIC-WRITE"); Record(name, "WRITE_OK"); } catch (Exception e) { Record(name, Failure(e)); }
    }
    static void Connect(string name, string ip, int port) {
        using (Socket s = new Socket(IPAddress.Parse(ip).AddressFamily, SocketType.Stream, ProtocolType.Tcp)) {
            try {
                IAsyncResult ar = s.BeginConnect(IPAddress.Parse(ip), port, null, null);
                if (!ar.AsyncWaitHandle.WaitOne(1500)) { Record(name, "TIMEOUT_NOT_DENIAL_PROOF"); return; }
                s.EndConnect(ar); Record(name, "CONNECTED_UNEXPECTEDLY");
            } catch (SocketException e) { Record(name, "SocketException:" + e.NativeErrorCode + ":" + e.SocketErrorCode); }
            catch (Exception e) { Record(name, Failure(e)); }
        }
    }
    static void Mailbox(string dir, int id, string request) {
        string req = Path.Combine(dir, "request" + id + ".json");
        string response = Path.Combine(dir, "response" + id + ".json");
        File.WriteAllText(req + ".tmp", request);
        File.Move(req + ".tmp", req);
        for (int i=0; i<100; i++) {
            if (File.Exists(response)) { Read("broker_response_" + id, response); return; }
            Thread.Sleep(25);
        }
        Record("broker_response_" + id, "TIMEOUT");
    }
    static int Main(string[] args) {
        log = Path.Combine(args[0], "child.tsv");
        try {
            IntPtr token; uint value, returned;
            if (!OpenProcessToken(GetCurrentProcess(), 8, out token)) return 91;
            if (!GetTokenInformation(token, 29, out value, 4, out returned)) return 92;
            CloseHandle(token); Record("TokenIsAppContainer", value.ToString());
            if (value != 1) return 93;
            Read("allowed_read", Path.Combine(args[1], "read-canary.txt"));
            Write("allowed_write", Path.Combine(args[0], "write-canary.txt"));
            Write("readonly_write_denied", Path.Combine(args[1], "forbidden-write.txt"));
            Read("protected_read_denied", Path.Combine(args[2], "protected-canary.txt"));
            Write("protected_write_denied", Path.Combine(args[2], "forbidden-write.txt"));
            Connect("loopback_allowed_service_direct_denied", "127.0.0.1", int.Parse(args[3]));
            Connect("loopback_other_service_direct_denied", "127.0.0.1", int.Parse(args[4]));
            Connect("ipv6_loopback_denied", "::1", int.Parse(args[5]));
            Connect("outbound_documentation_ip_denied", "192.0.2.1", 443);
            Mailbox(args[0], 1, "{\"op\":\"synthetic_ping\",\"request_id\":\"fixed-1\"}");
            Mailbox(args[0], 2, "{\"op\":\"fetch\",\"request_id\":\"fixed-2\",\"url\":\"http://127.0.0.1:" + args[4] + "/\"}");
            return 0;
        } catch (Exception e) {
            try { Record("fatal", Failure(e)); } catch {} return 94;
        }
    }
}
