using System.ComponentModel.DataAnnotations;

namespace IoTMonitoring.Api.Models;

/// <summary>
/// Payload posted by the ESP8266 uplink. Mirrors the JSON line emitted by the Uno R3.
/// Input-only, so it is an immutable record (bound case-insensitively from camelCase JSON).
/// </summary>
public record SensorReadingDto(
    [Required, DeviceId] string DeviceId,
    double Temperature,
    double Humidity,
    int Light,
    int LightPercent,
    double Battery,
    int BatteryPercent,
    long Sequence);
