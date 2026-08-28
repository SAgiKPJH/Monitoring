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
            Battery = dto.Battery,
            BatteryPercent = dto.BatteryPercent,
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

    /// <summary>
    /// 등록된 기기별 마지막 수신 시각과 경과 초. 데이터 끊김 감지·표시에 쓴다.
    /// knownDevices 에 있으나 한 번도 데이터가 없는 기기는 lastSeen=null, ageSeconds=-1 로 돌려준다
    /// (Grafana 에서 "아직 없음"과 "끊김"을 구분할 수 있게).
    /// </summary>
    public async Task<List<DeviceStatus>> GetStatusAsync(IEnumerable<string> knownDevices)
    {
        // deviceId 별 최신 timestamp 한 번에 집계
        var latest = await _collection.Aggregate()
            .Group(r => r.DeviceId, g => new { DeviceId = g.Key, Last = g.Max(x => x.Timestamp) })
            .ToListAsync();

        var map = latest.ToDictionary(x => x.DeviceId, x => x.Last);
        var now = DateTime.UtcNow;
        var result = new List<DeviceStatus>();

        // 알려진 기기 + 실제로 데이터가 있었던 기기를 합집합으로
        foreach (var id in knownDevices.Concat(map.Keys).Distinct())
        {
            if (map.TryGetValue(id, out var last))
            {
                var age = (long)(now - last).TotalSeconds;
                result.Add(new DeviceStatus
                {
                    DeviceId = id,
                    LastSeen = last,
                    AgeSeconds = age < 0 ? 0 : age,
                });
            }
            else
            {
                result.Add(new DeviceStatus { DeviceId = id, LastSeen = null, AgeSeconds = -1 });
            }
        }
        return result.OrderBy(r => r.DeviceId).ToList();
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
