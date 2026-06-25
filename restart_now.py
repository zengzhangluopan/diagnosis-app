import subprocess, os, time

# Kill existing process on 8501
result = subprocess.run('netstat -aon | findstr :8501 | findstr LISTENING', 
                       shell=True, capture_output=True, text=True)
for line in result.stdout.strip().split('\n'):
    if line:
        parts = line.strip().split()
        if parts:
            pid = parts[-1]
            os.system(f'taskkill /F /PID {pid} 2>nul')
            print(f'Killed PID {pid}')

time.sleep(2)

# Start streamlit detached
os.chdir(r'C:\Users\Yitian\diagnosis-app')
subprocess.Popen(
    ['python', '-m', 'streamlit', 'run', 'app.py', '--server.port', '8501'],
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
    stdout=open(os.devnull, 'w'),
    stderr=open(os.devnull, 'w')
)
print('Streamlit started on port 8501')
