using IoTMonitoring.Api.Models;
using MongoDB.Driver;

namespace IoTMonitoring.Api.Services;

public class ReadingsService
{
    private readonly IMongoCollection<SensorReading> _collection;

    public ReadingsService(MongoDbSettings settings)
    {
        var client = new MongoClient(settings.ConnectionString);
        var database = client.GetDatabase(settings.DatabaseName);
        _collection = database.GetCollection<SensorReading>(settings.CollectionName);

        // Idempotent: ensure the query index exists (mirrors the mongo init script).
        var indexKeys = Builders<SensorReading>.IndexKeys
            .Ascending(r => r.DeviceId)
            .Descending(r => r.Timestamp);
        _collection.Indexes.CreateOne(new CreateIndexModel<SensorReading>(indexKeys));
    }

    public async Task<SensorReading> CreateAsync(SensorReadingDto dto)
    {
        var reading = new SensorReading
        {
            DeviceId = dto.DeviceId,
            Temperature = dto.Temperature,
            Humidity = dto.Humidity,
            Light = dto.Light,
            LightPercent = dto.LightPercent,
            Sequence = dto.Sequence,
            Timestamp = DateTime.UtcNow
        };
        await _collection.InsertOneAsync(reading);
        return reading;
    }

    public async Task<List<SensorReading>> GetAsync(string? deviceId, DateTime? from, DateTime? to, int limit)
    {
        var fb = Builders<SensorReading>.Filter;
        var filter = fb.Empty;

        if (!string.IsNullOrWhiteSpace(deviceId))
            filter &= fb.Eq(r => r.DeviceId, deviceId);
        if (from.HasValue)
            filter &= fb.Gte(r => r.Timestamp, from.Value.ToUniversalTime());
        if (to.HasValue)
            filter &= fb.Lte(r => r.Timestamp, to.Value.ToUniversalTime());

        // Most recent N inside the range; Grafana re-sorts by the time column for plotting.
        return await _collection
            .Find(filter)
            .SortByDescending(r => r.Timestamp)
            .Limit(limit)
            .ToListAsync();
    }

    public async Task<SensorReading?> GetLatestAsync(string? deviceId)
    {
        var fb = Builders<SensorReading>.Filter;
        var filter = string.IsNullOrWhiteSpace(deviceId)
            ? fb.Empty
            : fb.Eq(r => r.DeviceId, deviceId);

        return await _collection
            .Find(filter)
            .SortByDescending(r => r.Timestamp)
            .FirstOrDefaultAsync();
    }
}
