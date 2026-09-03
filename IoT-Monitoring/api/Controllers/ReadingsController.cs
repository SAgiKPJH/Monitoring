using IoTMonitoring.Api.Models;
using IoTMonitoring.Api.Services;
using Microsoft.AspNetCore.Mvc;

namespace IoTMonitoring.Api.Controllers;

[ApiController]
[Route("api/readings")]
public class ReadingsController : ControllerBase
{
    private readonly ReadingsService _service;
    private readonly IConfiguration _config;
    private readonly ILogger<ReadingsController> _logger;

    public ReadingsController(ReadingsService service, IConfiguration config, ILogger<ReadingsController> logger)
    {
        _service = service;
        _config = config;
        _logger = logger;
    }

    // POST /api/readings  — called by the ESP8266 uplink.
    [HttpPost]
    public async Task<IActionResult> Post([FromBody] SensorReadingDto dto)
    {
        var configuredKey = _config["Api:ApiKey"];
        if (!string.IsNullOrEmpty(configuredKey))
        {
            var provided = Request.Headers["X-Api-Key"].ToString();
            if (provided != configuredKey)
                return Unauthorized(new { error = "invalid api key" });
        }

        if (dto is null || string.IsNullOrWhiteSpace(dto.DeviceId))
            return BadRequest(new { error = "deviceId required" });

        var saved = await _service.CreateAsync(dto);
        _logger.LogInformation(
            "Stored reading device={DeviceId} seq={Seq} t={Temp} h={Hum} light={Light}",
            saved.DeviceId, saved.Sequence, saved.Temperature, saved.Humidity, saved.Light);

        return StatusCode(StatusCodes.Status201Created, saved);
    }

    // GET /api/readings?deviceId=&from=&to=&limit=  — used by Grafana (Infinity datasource).
    [HttpGet]
    public async Task<IActionResult> Get(
        [FromQuery] string? deviceId,
        [FromQuery] DateTime? from,
        [FromQuery] DateTime? to,
        [FromQuery] int limit = 5000)
    {
        if (limit <= 0 || limit > 50000) limit = 5000;
        var readings = await _service.GetAsync(deviceId, from, to, limit);
        return Ok(readings);
    }

    // GET /api/readings/status?devices=BRB,MR,RO,TO,BRO   (devices 순서 = 응답 순서)
    //   기기별 마지막 수신 경과 시간 + 한 줄 요약. 연결 상태 패널과 "데이터 끊김" 알림이 사용.
    [HttpGet("status")]
    public async Task<IActionResult> GetStatus([FromQuery] string? devices,
                                              [FromQuery] bool onlyKnown = false)
    {
        var known = (devices ?? "BRB,MR,RO,TO,BRO")
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

        var list = await _service.GetStatusAsync(known, onlyKnown);

        // 알림 메시지에 그대로 넣을 한 줄 요약:  BRB ✅ · BRO ❌ · TO ⚠️ ...
        var summary = string.Join(" · ", list.Select(d => $"{d.DeviceId} {d.Icon}"));
        var offline = list.Where(d => d.State == "offline").Select(d => d.DeviceId).ToArray();
        var stale = list.Where(d => d.State == "stale").Select(d => d.DeviceId).ToArray();

        return Ok(new
        {
            summary,
            offlineCount = offline.Length,
            staleCount = stale.Length,
            offline,
            stale,
            devices = list.Select(d => new
            {
                d.DeviceId,
                d.LastSeen,
                d.AgeSeconds,
                d.AgeMinutes,
                d.State,
                d.Icon,
            }),
        });
    }

    // GET /api/readings/latest?deviceId=&maxAgeMinutes=
    //   maxAgeMinutes 가 주어지면 그보다 오래된 값은 "데이터 없음"과 동일하게 취급한다
    //   (평면도에서 1시간 이상 끊긴 노드를 '-' 로 보이게).
    [HttpGet("latest")]
    public async Task<IActionResult> GetLatest([FromQuery] string? deviceId,
                                               [FromQuery] int? maxAgeMinutes = null)
    {
        var reading = await _service.GetLatestAsync(deviceId);
        var tooOld = reading is not null && maxAgeMinutes > 0
            && reading.Timestamp < DateTime.UtcNow.AddMinutes(-maxAgeMinutes.Value);

        if (reading is null || tooOld)
        {
            // No (or stale) data: return 200 with null fields so Grafana Canvas shows
            // the "No value" placeholder ("-") instead of "Field Not Found".
            return Ok(new
            {
                deviceId = deviceId ?? "",
                temperature = (double?)null,
                humidity = (double?)null,
                light = (int?)null,
                lightPercent = (int?)null,
                battery = (double?)null,
                batteryPercent = (int?)null,
                sequence = (long?)null,
                timestamp = (DateTime?)null
            });
        }
        return Ok(reading);
    }
}
