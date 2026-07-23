using System.ComponentModel.DataAnnotations;

namespace IoTMonitoring.Api.Models;

/// <summary>
/// Error report posted by the ESP8266 uplink (POST /api/errors). Mirrors the JSON line
/// the Uno emits for an error packet: {"type":"error","deviceId":..,"errorCode":..,"sequence":..}.
/// The extra "type" field is ignored during binding.
/// </summary>
public record ErrorReportDto(
    [Required] string DeviceId,
    int ErrorCode,
    long Sequence);
