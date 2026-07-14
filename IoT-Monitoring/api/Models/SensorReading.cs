using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace IoTMonitoring.Api.Models;

/// <summary>
/// Document stored in the MongoDB "readings" collection.
/// </summary>
public class SensorReading
{
    [BsonId]
    [BsonRepresentation(BsonType.ObjectId)]
    public string? Id { get; set; }

    [BsonElement("deviceId")]
    public string DeviceId { get; set; } = "unknown";

    [BsonElement("temperature")]
    public double Temperature { get; set; }

    [BsonElement("humidity")]
    public double Humidity { get; set; }

    [BsonElement("light")]
    public int Light { get; set; }

    [BsonElement("lightPercent")]
    public int LightPercent { get; set; }

    [BsonElement("battery")]
    public double Battery { get; set; }

    [BsonElement("batteryPercent")]
    public int BatteryPercent { get; set; }

    [BsonElement("sequence")]
    public long Sequence { get; set; }

    [BsonElement("timestamp")]
    public DateTime Timestamp { get; set; }
}
