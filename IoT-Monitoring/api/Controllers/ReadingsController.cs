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

    // GET /api/readings/latest?deviceId=
    [HttpGet("latest")]
    public async Task<IActionResult> GetLatest([FromQuery] string? deviceId)
    {
        var reading = await _service.GetLatestAsync(deviceId);
        if (reading is null)
        {
            // No data yet for this device: return 200 with null fields so Grafana Canvas shows
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
