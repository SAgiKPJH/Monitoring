using IoTMonitoring.Api.Models;
using IoTMonitoring.Api.Services;
using Microsoft.AspNetCore.Mvc;

namespace IoTMonitoring.Api.Controllers;

[ApiController]
[Route("api/errors")]
public class ErrorsController : ControllerBase
{
    private readonly ErrorsService _service;
    private readonly IConfiguration _config;
    private readonly ILogger<ErrorsController> _logger;

    public ErrorsController(ErrorsService service, IConfiguration config, ILogger<ErrorsController> logger)
    {
        _service = service;
        _config = config;
        _logger = logger;
    }

    // POST /api/errors  — called by the ESP8266 uplink when a node reports a fault.
    [HttpPost]
    public async Task<IActionResult> Post([FromBody] ErrorReportDto dto)
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
        _logger.LogWarning(
            "Node error device={DeviceId} code={Code} ({Message}) seq={Seq}",
            saved.DeviceId, saved.ErrorCode, saved.Message, saved.Sequence);

        return StatusCode(StatusCodes.Status201Created, saved);
    }

    // GET /api/errors?deviceId=&from=&to=&limit=  — list stored faults (Grafana / ops).
    [HttpGet]
    public async Task<IActionResult> Get(
        [FromQuery] string? deviceId,
        [FromQuery] DateTime? from,
        [FromQuery] DateTime? to,
        [FromQuery] int limit = 1000)
    {
        if (limit <= 0 || limit > 50000) limit = 1000;
        var errors = await _service.GetAsync(deviceId, from, to, limit);
        return Ok(errors);
    }

    // GET /api/errors/latest?deviceId=
    [HttpGet("latest")]
    public async Task<IActionResult> GetLatest([FromQuery] string? deviceId)
    {
        var report = await _service.GetLatestAsync(deviceId);
        if (report is null)
        {
            // No fault yet: return 200 with null fields (so Grafana shows "-" not an error).
            return Ok(new
            {
                deviceId = deviceId ?? "",
                errorCode = (int?)null,
                message = (string?)null,
                sequence = (long?)null,
                timestamp = (DateTime?)null
            });
        }
        return Ok(report);
    }
}
