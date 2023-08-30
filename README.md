문서정보 : 2023.08.25.~ 작성, 작성자 [@SAgiKPJH](https://github.com/SAgiKPJH)

<br>

# Monitoring
모니터링에 대한 모든 할 수 있는 내용을 정리합니다.

### 목표
- [x] : [Process Poweshell 모니터링](#process-poweshell-모니터링)
- [x] : Docker Grafana Prometeus 활용한 모니터링

### 제작자
[@SAgiKPJH](https://github.com/SAgiKPJH)

<br><br>

---

<br><br>


# Process Poweshell 모니터링

- PowerShell로 특정 Process의 CPU 사용량 및 메모리 사용량을 획득합니다.
- 기본적인 명령어는 다음과 같습니다.  
  ```shell
  Get-Process

  Get-Process -Name notepad
  ```
  ![image](https://github.com/SagiK-Repository/Monitoring/assets/66783849/9fb05ba6-b4af-4cac-865e-d857d9fee276)  
- 다음과 같이 특정 프로세스의 CPU, Memory 사용량을 획득할 수 있습니다.
  ```shell
  (Get-Process -name PBM_Reader).CPU
  (Get-Process -name PBM_Reader).WorkingSet
  ```
  ![image](https://github.com/SagiK-Repository/Monitoring/assets/66783849/57051bbf-25d7-41ca-a707-c3ec17971d1a)
- Power Shell에서 다음과 같이 코드를 구성하여 CPU 및 Memory 사용량을 획득할 수 있습니다.
  ```shell
  while ($true) {
    $process = Get-Process -Name notepad
    Write-Host "CPU Usage: $($process.CPU)"
    Write-Host "Memory Usage: $($process.WorkingSet)"
    Start-Sleep -Seconds 5
  }
  ```
  ![image](https://github.com/SagiK-Repository/Monitoring/assets/66783849/d08b8ffe-63a1-408c-96cf-b76c33ed0c53)
- 이를 파일로 저장하면 다음과 같습니다.  
  ```shell
  $LogFilePath = ".\PBM_Reader_Usage_Log.txt"
  
  while ($true) {
      $process = Get-Process -Name PBM_Reader
      $CurrentTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
      $CPUUsage = $process.CPU
      $MemoryUsage = $process.WorkingSet
  
      $Output = "$CurrentTime	CPU Usage:	 $CPUUsage 	Memory Usage:	 $MemoryUsage"

      # 로그 파일에 기록
      Add-Content -Path $LogFilePath -Value $Output

      # 화면에 출력
      Write-Host $Output
      Write-Host ""
  
      Start-Sleep -Seconds 5
  }
  ```
- 이를 (.ps1) 파일로 저장하여 스크립트 파일로 만들어 실행할 수 있도록 합니다.  
  ![image](https://github.com/SagiK-Repository/Monitoring/assets/66783849/02c33b6e-8cae-4fce-a903-72ac148fb632)


<br><br>

# Docker Grafana Prometeus 활용한 모니터링

- PC의 CPU, Memory 사용량 등을 모니터링합니다.
- 기본적으로 다음과 같이 모니터링을 진행합니다.
  1. Docker로 띄운 NodeExporter(PC 정보 수집, Prometeus 제공 프로그램 사용)로 정보 수집
  2. Docker로 띄운 Prometeus로 정보 전송
  3. Docker로 띄운 Grafana로 정보 모니터링
 
* 참조 사이트 : https://developer-nyong.tistory.com/49

- 위 세가지 조건을 만족하도록 Docker-compose를 작성합니다. (docker-compose.yml)
  ```yml
  version: '3'
  services:
    node-exporter:
      image: prom/node-exporter
      ports:
        - 9100:9100

    prometheus:
      image: prom/prometheus
      ports:
        - 9090:9090
      volumes:
        - ./prometheus.yml:/etc/prometheus/prometheus.yml

    grafana:
      image: grafana/grafana
      ports:
        - 3000:3000

  networks:
    promnet:
      driver: bridge
  ```
- 그리고 prometeus.yml을 작성하여 환경을 설정합니다.
  ```yml
  global:
    scrape_interval:     15s

  scrape_configs:
    - job_name: 'node-exporter'
      static_configs:
        - targets: ['node-exporter:9100']
  ```
- 다음 명령어를 통해 실행합니다.
  ```shell
  cd "Docker-Compose Directory"
  docker-compose -f docker-compose.yml up -d
  ```  
  - 다음과 같이 설치가 되며 실행 됩니다.  
  <img src="https://github.com/SagiK-Repository/Monitoring/assets/66783849/b6d61196-cbf1-46cd-aaa3-0f2bea272548"/>  
  <img src="https://github.com/SagiK-Repository/Monitoring/assets/66783849/b36b72c0-6e44-4335-9252-605d0489f9d9"/>  
- 웹브라우저를 통해 node-expoter에 접속(http://localhost:9100/metrics)하여 정상 수집하고 있는지 확인합니다.
- 웹브라우저를 통해 Prometeus의 Port로 접속(http://127.0.0.1:9090) -> Status > Targets > node-exporter를 확인합니다.  
  <img src="https://github.com/SagiK-Repository/Monitoring/assets/66783849/8c94ea7c-4d85-4d04-b251-644234828bf7"/>  
- 마찬가지로 Grafana로 접속(http://127.0.0.1:3000), Login admin/admin, Menu > Dashboards > New > Imports > 1860 입력 > Load > Import >
  - 프로메테우스 미설정시 : prometeus - Configure a new data source > Prometeus > URL 입력 (127.0.0.1 또는 LocalHost가 아닌 IP번호를 입력해야 합니다) > Save & Test  
  <img src="https://github.com/SagiK-Repository/Monitoring/assets/66783849/5b979031-3e98-47fb-8b64-cbee7b0c6cca"/>  
  <img src="https://github.com/SagiK-Repository/Monitoring/assets/66783849/f5211d3e-deca-4299-a2a0-bd2091c571f0"/>





