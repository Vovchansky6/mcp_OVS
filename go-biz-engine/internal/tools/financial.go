package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"sort"
	"strings"
	"time"
)

type FinancialParams struct {
	BaseCurrency  string  `json:"base_currency"`          // например "USD"
	QuoteCurrency string  `json:"quote_currency"`         // например "EUR"
	Days          int     `json:"days"`                   // период в днях (N последних дней)
	Amount        float64 `json:"amount,omitempty"`       // опционально, пока не используем
}

type DailyRate struct {
	Date string  `json:"date"` // "2025-12-01"
	Rate float64 `json:"rate"` // курс quote к base на эту дату
}

type FinancialResult struct {
	RateAvg    float64     `json:"rate_avg"`
	RateMin    float64     `json:"rate_min"`
	RateMax    float64     `json:"rate_max"`
	Volatility float64     `json:"volatility"` // стандартное отклонение дневных курсов
	Raw        []DailyRate `json:"raw"`        // сырые данные по дням
}

const frankfurterBaseURL = "https://api.frankfurter.dev"

var httpClient = &http.Client{
	Timeout: 10 *time.Second,
}

// структура ответа Frankfurter для тайм-серий
type frankfurterTimeSeriesResponse struct {
	Base      string                        `json:"base"`
	StartDate string                        `json:"start_date"`
	EndDate   string                        `json:"end_date"`
	Rates     map[string]map[string]float64 `json:"rates"` // "2024-01-02": { "USD": 1.09 }
}

func ExecuteFinancialAnalyzer(ctx context.Context, params FinancialParams) (FinancialResult, error) {
	base := strings.ToUpper(strings.TrimSpace(params.BaseCurrency))
	quote := strings.ToUpper(strings.TrimSpace(params.QuoteCurrency))

	if base == "" || quote == "" {
		return FinancialResult{}, fmt.Errorf("base_currency and quote_currency are required")
	}
	if params.Days <= 0 {
		return FinancialResult{}, fmt.Errorf("days must be > 0")
	}

	// считаем период: от сегодня - (days-1) до сегодня (UTC)
	end := time.Now().UTC()
	start := end.AddDate(0, 0, -params.Days+1)

	startStr := start.Format("2006-01-02")
	endStr := end.Format("2006-01-02")

	// пример: /v1/2024-01-01..2024-01-31?base=USD&symbols=EUR
	url := fmt.Sprintf("%s/v1/%s..%s?base=%s&symbols=%s",
		frankfurterBaseURL, startStr, endStr, base, quote)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return FinancialResult{}, fmt.Errorf("create request: %w", err)
	}

	resp, err := httpClient.Do(req)
	if err != nil {
		return FinancialResult{}, fmt.Errorf("call frankfurter: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return FinancialResult{}, fmt.Errorf("frankfurter returned status %d", resp.StatusCode)
	}

	var apiResp frankfurterTimeSeriesResponse
	if err := json.NewDecoder(resp.Body).Decode(&apiResp); err != nil {
		return FinancialResult{}, fmt.Errorf("decode frankfurter response: %w", err)
	}

	// вытаскиваем список DailyRate
	rates := make([]DailyRate, 0, len(apiResp.Rates))
	for date, m := range apiResp.Rates {
		rate, ok := m[quote]
		if !ok {
			continue
		}
		rates = append(rates, DailyRate{
			Date: date,
			Rate: rate,
		})
	}

	if len(rates) == 0 {
		return FinancialResult{}, fmt.Errorf("no rates returned for %s/%s", base, quote)
	}

	// сортируем по дате (строка в ISO-формате, поэтому лексикографический порядок == хронологический)
	sort.Slice(rates, func(i, j int) bool {
		return rates[i].Date < rates[j].Date
	})

	// считаем метрики
	sum := 0.0
	min := rates[0].Rate
	max := rates[0].Rate

	for _, r := range rates {
		v := r.Rate
		sum += v
		if v < min {
			min = v
		}
		if v > max {
			max = v
		}
	}

	n := float64(len(rates))
	avg := sum / n

	// волатильность как стандартное отклонение
	var varSum float64
	for _, r := range rates {
		diff := r.Rate - avg
		varSum += diff * diff
	}
	volatility := math.Sqrt(varSum / n)

	result := FinancialResult{
		RateAvg:    avg,
		RateMin:    min,
		RateMax:    max,
		Volatility: volatility,
		Raw:        rates,
	}

	return result, nil
}
