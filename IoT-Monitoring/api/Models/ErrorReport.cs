using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace IoTMonitoring.Api.Models;

/// <summary>
/// Document stored in the MongoDB "errors" collection — a fault reported by a node
/// (the Pico blinks, sends this over NRF, then resets).
/// </summary>
public class ErrorReport
{
    [BsonId]
    [BsonRepresentation(BsonType.ObjectId)]
    public string? Id { get; set; }

    [BsonElement("deviceId")]
    public DeviceId DeviceId { get; set; }

    [BsonElement("errorCode")]
    public int ErrorCode { get; set; }

    [BsonElement("message")]
    public string Message { get; set; } = "";

    [BsonElement("sequence")]
    public long Sequence { get; set; }

    [BsonElement("timestamp")]
    public DateTime Timestamp { get; set; }
}
