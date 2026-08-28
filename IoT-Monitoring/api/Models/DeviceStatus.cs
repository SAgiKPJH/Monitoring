namespace IoTMonitoring.Api.Models;

/// <summary>
/// 기기별 마지막 수신 상태. Grafana 의 연결 상태 패널과 "데이터 끊김" 알림이 사용한다.
/// </summary>
public class DeviceStatus
{
    public string DeviceId { get; set; } = "";

    /// <summary>마지막 수신 시각(UTC). 한 번도 없었으면 null.</summary>
    public DateTime? LastSeen { get; set; }

    /// <summary>마지막 수신 후 경과 초. 데이터가 없으면 -1.</summary>
    public long AgeSeconds { get; set; }

    /// <summary>경과 분 (알림 임계값 비교용).</summary>
    public double AgeMinutes => AgeSeconds < 0 ? -1 : Math.Round(AgeSeconds / 60.0, 1);

    /// <summary>online / stale(30분↑) / offline(60분↑) / nodata</summary>
    public string State =>
        AgeSeconds < 0 ? "nodata" :
        AgeSeconds >= 3600 ? "offline" :
        AgeSeconds >= 1800 ? "stale" : "online";

    /// <summary>대시보드·알림에 그대로 쓰는 아이콘.</summary>
    public string Icon => State switch
    {
        "online" => "✅",
        "stale" => "⚠️",
        "offline" => "❌",
        _ => "➖",
    };
}
