namespace IoTMonitoring.Api.Services;

public class MongoDbSettings
{
    public string ConnectionString { get; set; } = "mongodb://localhost:27017";
    public string DatabaseName { get; set; } = "monitoring";
    public string CollectionName { get; set; } = "readings";
}
