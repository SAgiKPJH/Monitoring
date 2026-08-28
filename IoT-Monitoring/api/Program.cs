using IoTMonitoring.Api.Services;

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
        "GET  /api/readings/latest?deviceId=",
        "GET  /api/readings/status?devices=BRB,BRO,TO,RO,MR",
        "POST /api/errors",
        "GET  /api/errors?deviceId=&from=&to=&limit=",
        "GET  /api/errors/latest?deviceId=",
        "GET  /health"
    }
}));

app.MapGet("/health", () => Results.Ok(new { status = "ok" }));

app.MapControllers();

app.Run();
