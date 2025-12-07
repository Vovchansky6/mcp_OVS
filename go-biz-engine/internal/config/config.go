package config

import (
	"bufio"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"strings"
)

type Config struct {
	Port         string
	PublicAPIURL string
	APIKey       string
	Env          string // например: dev / prod
	Version      string // версия сервиса
}

// Load загружает .env (если есть) и читает переменные окружения.
func Load() (*Config, error) {
	_ = loadDotEnv(".env") // отсутствие файла не считаем ошибкой

	cfg := &Config{
		Port:         getEnv("BIZ_ENGINE_PORT", "8080"),
		PublicAPIURL: getEnv("BIZ_ENGINE_PUBLIC_API_URL", ""),
		APIKey:       getEnv("BIZ_ENGINE_API_KEY", ""),
		Env:          getEnv("BIZ_ENGINE_ENV", "dev"),
		Version:      getEnv("BIZ_ENGINE_VERSION", "go-biz-engine/0.1.0"),
	}

	if cfg.PublicAPIURL == "" {
		// Можно не падать, но для примера сделаем обязательным
		return nil, fmt.Errorf("BIZ_ENGINE_PUBLIC_API_URL is required")
	}

	return cfg, nil
}

// примитивный парсер .env
func loadDotEnv(path string) error {
	f, err := os.Open(path)
	if err != nil {
		if errors.Is(err, fs.ErrNotExist) {
			return nil
		}
		return err
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		val := strings.TrimSpace(parts[1])
		// убираем кавычки, если есть
		val = strings.Trim(val, `"'`)
		_ = os.Setenv(key, val)
	}

	return scanner.Err()
}

func getEnv(key, def string) string {
	if v, ok := os.LookupEnv(key); ok {
		return v
	}
	return def
}
