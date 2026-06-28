# ---- build stage ----
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

COPY IoTMonitoring.Api.csproj ./
RUN dotnet restore IoTMonitoring.Api.csproj

COPY . ./
RUN dotnet publish IoTMonitoring.Api.csproj -c Release -o /app/publish /p:UseAppHost=false

# ---- runtime stage ----
FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS final
WORKDIR /app
COPY --from=build /app/publish ./

ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080

ENTRYPOINT ["dotnet", "IoTMonitoring.Api.dll"]
