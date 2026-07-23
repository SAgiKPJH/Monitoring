using IoTMonitoring.Api.Models;
using MongoDB.Driver;

namespace IoTMonitoring.Api.Services;

public class ErrorsService
{
    private readonly IMongoCollection<ErrorReport> _collection;

    // errorCode -> human message. Keep in sync with the Pico/Uno firmware error codes.
    private static readonly Dictionary<int, string> Messages = new()
    {
        [1] = "AM2320 sensor read failed",
        [2] = "NRF24L01 radio init failed",
    };

    public static string DescribeCode(int code) =>
        Messages.TryGetValue(code, out var m) ? m : $"unknown error (code {code})";

    public ErrorsService(MongoDbSettings settings)
    {
        var client = new MongoClient(settings.ConnectionString);
        var database = client.GetDatabase(settings.DatabaseName);
        _collection = database.GetCollection<ErrorReport>(settings.ErrorsCollectionName);

        // Idempotent: ensure the query index (and the collection) exist.
        var indexKeys = Builders<ErrorReport>.IndexKeys
            .Ascending(r => r.DeviceId)
            .Descending(r => r.Timestamp);
        _collection.Indexes.CreateOne(new CreateIndexModel<ErrorReport>(indexKeys));
    }

    public async Task<ErrorReport> CreateAsync(ErrorReportDto dto)
    {
        var report = new ErrorReport
        {
            DeviceId = dto.DeviceId,
            ErrorCode = dto.ErrorCode,
            Message = DescribeCode(dto.ErrorCode),
            Sequence = dto.Sequence,
            Timestamp = DateTime.UtcNow
        };
        await _collection.InsertOneAsync(report);
        return report;
    }

    public async Task<List<ErrorReport>> GetAsync(string? deviceId, DateTime? from, DateTime? to, int limit)
    {
        var fb = Builders<ErrorReport>.Filter;
        var filter = fb.Empty;

        if (!string.IsNullOrWhiteSpace(deviceId))
            filter &= fb.Eq(r => r.DeviceId, deviceId);
        if (from.HasValue)
            filter &= fb.Gte(r => r.Timestamp, from.Value.ToUniversalTime());
        if (to.HasValue)
            filter &= fb.Lte(r => r.Timestamp, to.Value.ToUniversalTime());

        return await _collection
            .Find(filter)
            .SortByDescending(r => r.Timestamp)
            .Limit(limit)
            .ToListAsync();
    }

    public async Task<ErrorReport?> GetLatestAsync(string? deviceId)
    {
        var fb = Builders<ErrorReport>.Filter;
        var filter = string.IsNullOrWhiteSpace(deviceId)
            ? fb.Empty
            : fb.Eq(r => r.DeviceId, deviceId);

        return await _collection
            .Find(filter)
            .SortByDescending(r => r.Timestamp)
            .FirstOrDefaultAsync();
    }
}
