using System.ComponentModel.DataAnnotations;
using System.Text.Json;
using System.Text.Json.Serialization;
using MongoDB.Bson;
using MongoDB.Bson.Serialization;

namespace IoTMonitoring.Api.Models;

/// <summary>
/// 노드 식별자 값 객체. deviceId 규칙을 이 타입 하나가 소유한다(단일 진실 공급원).
///
/// 규칙은 펌웨어 제약에서 온다:
///   Pico   : DEVICE_ID = "BRB"   (&lt;= 5 chars)
///   페이로드: char deviceId[6]    = 5글자 + 널 종료
/// 따라서 <b>영숫자 1~5자</b>만 허용한다.
///
/// 엄격/관대를 경로에 따라 나눈다:
///   · <b>쓰기</b>(새로 들어오는 값) — 생성자가 <see cref="ArgumentException"/> 을 던져 쓰레기를 막는다.
///   · <b>읽기</b>(DB 의 과거 값) — <see cref="FromStorage"/> 는 검증하지 않는다.
///     NRF 접촉 불량 시절 저장된 "!" · "xxxxxx" 때문에 조회가 500 으로 죽으면 안 되기 때문.
/// </summary>
[JsonConverter(typeof(DeviceIdJsonConverter))]
public readonly record struct DeviceId
{
    public const int MaxLength = 5;

    public string Value { get; }

    /// <exception cref="ArgumentException">규칙 위반 시.</exception>
    public DeviceId(string? value)
    {
        if (!IsValid(value, out var error))
            throw new ArgumentException(error, nameof(value));
        Value = value!;
    }

    private DeviceId(string value, bool _) => Value = value;   // 검증 우회(저장소 전용)

    /// <summary>저장소에서 읽은 값. 과거 데이터가 규칙을 어겨도 예외를 던지지 않는다.</summary>
    public static DeviceId FromStorage(string? value) => new(value ?? "", false);

    public static bool TryCreate(string? value, out DeviceId id)
    {
        if (IsValid(value, out _)) { id = new DeviceId(value); return true; }
        id = default;
        return false;
    }

    public static bool IsValid(string? value) => IsValid(value, out _);

    public static bool IsValid(string? value, out string error)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            error = "deviceId 는 비워 둘 수 없습니다.";
            return false;
        }
        if (value.Length > MaxLength)
        {
            error = $"deviceId 는 최대 {MaxLength}자입니다 (펌웨어 payload 제약). 받은 길이: {value.Length}";
            return false;
        }
        foreach (var c in value)
        {
            if (!char.IsAsciiLetterOrDigit(c))
            {
                error = $"deviceId 는 영숫자만 허용합니다. 허용되지 않는 문자: '{c}'";
                return false;
            }
        }
        error = "";
        return true;
    }

    /// <summary>이 인스턴스가 규칙을 만족하는지 (저장소에서 읽은 값 판별용).</summary>
    public bool IsWellFormed => IsValid(Value);

    public override string ToString() => Value;

    public static implicit operator string(DeviceId id) => id.Value;
}

/// <summary>JSON 에서 평범한 문자열로 오간다 ("BRB" ↔ DeviceId).</summary>
public sealed class DeviceIdJsonConverter : JsonConverter<DeviceId>
{
    public override DeviceId Read(ref Utf8JsonReader r, Type t, JsonSerializerOptions o)
        => new(r.GetString());                       // 입력이므로 엄격하게 검증

    public override void Write(Utf8JsonWriter w, DeviceId v, JsonSerializerOptions o)
        => w.WriteStringValue(v.Value);
}

/// <summary>MongoDB 에도 평범한 문자열로 저장한다. 읽을 때는 검증하지 않는다(과거 데이터 보호).</summary>
public sealed class DeviceIdBsonSerializer : IBsonSerializer<DeviceId>
{
    public Type ValueType => typeof(DeviceId);

    public DeviceId Deserialize(BsonDeserializationContext ctx, BsonDeserializationArgs args)
    {
        var reader = ctx.Reader;
        if (reader.GetCurrentBsonType() == BsonType.Null) { reader.ReadNull(); return DeviceId.FromStorage(""); }
        return DeviceId.FromStorage(reader.ReadString());
    }

    public void Serialize(BsonSerializationContext ctx, BsonSerializationArgs args, DeviceId value)
        => ctx.Writer.WriteString(value.Value);

    object IBsonSerializer.Deserialize(BsonDeserializationContext c, BsonDeserializationArgs a)
        => Deserialize(c, a);

    public void Serialize(BsonSerializationContext c, BsonSerializationArgs a, object value)
        => Serialize(c, a, (DeviceId)value);
}

/// <summary>DTO 의 deviceId(string) 검증을 <see cref="DeviceId"/> 규칙에 위임한다.</summary>
public sealed class DeviceIdAttribute : ValidationAttribute
{
    protected override ValidationResult? IsValid(object? value, ValidationContext ctx)
        => DeviceId.IsValid(value as string, out var error)
            ? ValidationResult.Success
            : new ValidationResult(error, new[] { ctx.MemberName ?? "DeviceId" });
}
