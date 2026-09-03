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
            DeviceId = new DeviceId(dto.DeviceId),   // 새 값이므로 엄격 검증
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
            filter &= fb.Eq(r => r.DeviceId, DeviceId.FromStorage(deviceId));
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
    public async Task<List<DeviceStatus>> GetStatusAsync(IEnumerable<string> knownDevices, bool onlyKnown = false)
    {
        // deviceId 별 최신 timestamp 한 번에 집계
        var latest = await _collection.Aggregate()
            .Group(r => r.DeviceId, g => new { DeviceId = g.Key, Last = g.Max(x => x.Timestamp) })
            .ToListAsync();

        var map = latest.ToDictionary(x => x.DeviceId.Value, x => x.Last);
        var now = DateTime.UtcNow;
        var result = new List<DeviceStatus>();

        // 기본은 "요청 목록 + DB 에서 발견된 기기" 합집합 → 새 노드를 추가하면 설정 없이 자동으로 잡힌다.
        var raw = onlyKnown
            ? knownDevices.Distinct().ToList()
            : knownDevices.Concat(map.Keys).Distinct().ToList();

        foreach (var rawId in raw)
        {
            if (!DeviceId.TryCreate(rawId, out var id))
                continue;                     // 과거 손상 데이터("!" · "xxxxxx")는 표시에서 제외

            var hasData = map.TryGetValue(rawId, out var last);
            var age = hasData ? (long)(now - last).TotalSeconds : -1;
            result.Add(new DeviceStatus(id, hasData ? last : null, age));
        }
        // 표시 순서: 요청 목록(knownDevices) 순서를 그대로 유지하고,
        // 목록에 없는(자동 발견) 기기는 그 뒤에 알파벳순으로 붙인다.
        var order = new Dictionary<string, int>(StringComparer.Ordinal);
        var idx = 0;
        foreach (var d in knownDevices)
            if (!order.ContainsKey(d)) order[d] = idx++;

        return result
            .OrderBy(r => order.TryGetValue(r.DeviceId.Value, out var i) ? i : int.MaxValue)
            .ThenBy(r => r.DeviceId.Value, StringComparer.Ordinal)
            .ToList();
    }

    public async Task<SensorReading?> GetLatestAsync(string? deviceId)
    {
        var fb = Builders<SensorReading>.Filter;
        var filter = string.IsNullOrWhiteSpace(deviceId)
            ? fb.Empty
            : fb.Eq(r => r.DeviceId, DeviceId.FromStorage(deviceId));

        return await _collection
            .Find(filter)
            .SortByDescending(r => r.Timestamp)
            .FirstOrDefaultAsync();
    }
}
