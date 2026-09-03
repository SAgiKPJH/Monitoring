using IoTMonitoring.Api.Models;
using IoTMonitoring.Api.Services;
using MongoDB.Bson.Serialization;

// DeviceId 값 객체를 MongoDB 에 평범한 문자열로 저장/조회한다.
BsonSerializer.RegisterSerializer(typeof(DeviceId), new DeviceIdBsonSerializer());

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();

// MongoDB settings — bound from configuration / environment.
// Override in Docker via env vars, e.g. MongoDb__ConnectionString=...
var mongoSettings = builder.Configuration.GetSection("MongoDb").Get<MongoDbSettings>()
                    ?? new MongoDbSettings();
builder.Services.AddSingleton(mongoSettings);
builder.Services.AddSingleton<ReadingsService>();
builder.Services.AddSingleton<ErrorsService>();

// Allow Grafana (and any browser client) to query the API.
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
        policy.AllowAnyOrigin().AllowAnyHeader().AllowAnyMethod());
});

var app = builder.Build();

app.UseCors();

// Simple landing page that documents the available routes.
app.MapGet("/", () => Results.Ok(new
{
    name = "IoT Monitoring API",
    endpoints = new[]
    {
        "POST /api/readings",
        "GET  /api/readings?deviceId=&from=&to=&limit=",
        "GET  /api/readings/latest?deviceId=&maxAgeMinutes=",
        "GET  /api/readings/status?devices=BRB,MR,RO,TO,BRO",
        "POST /api/errors",
        "GET  /api/errors?deviceId=&from=&to=&limit=",
        "GET  /api/errors/latest?deviceId=",
        "GET  /health"
    }
}));

app.MapGet("/health", () => Results.Ok(new { status = "ok" }));

app.MapControllers();

app.Run();
