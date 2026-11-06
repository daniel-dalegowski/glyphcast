from glyphcast.conditions import IconKind, classify


def test_clear_sky():
    c = classify(code=0, rain_amount=0.0, snow_amount=0.0, wind_speed=5.0, cloud_cover=0.0, wind_threshold=25)
    assert c.kind is IconKind.CLEAR
    assert c.wind_overlay is False


def test_heavy_rain_code_with_light_actual_rain_stays_moderate():
    # code 65 = "heavy rain" baseline intensity 0.85, but if almost nothing
    # is actually falling right now the blend shouldn't drag it down below
    # the code's own baseline (max(), not average).
    c = classify(code=65, rain_amount=0.1, snow_amount=0.0, wind_speed=5.0, cloud_cover=50.0, wind_threshold=25)
    assert c.kind is IconKind.RAIN
    assert c.intensity >= 0.85


def test_light_rain_code_with_heavy_actual_rain_reads_heavier():
    c = classify(code=61, rain_amount=8.0, snow_amount=0.0, wind_speed=5.0, cloud_cover=50.0, wind_threshold=25)
    assert c.kind is IconKind.RAIN
    assert c.intensity == 1.0  # 8mm/h clamps to the max scale (metric, hourly)


def test_snow_amount_drives_snow_intensity_not_rain():
    c = classify(code=71, rain_amount=0.0, snow_amount=5.0, wind_speed=5.0, cloud_cover=50.0, wind_threshold=25)
    assert c.kind is IconKind.SNOW
    assert c.intensity == 1.0  # 5cm clamps to the max metric hourly snow scale


def test_daily_scale_differs_from_hourly_scale():
    hourly = classify(code=61, rain_amount=5.0, snow_amount=0.0, wind_speed=5.0, cloud_cover=50.0,
                       wind_threshold=25, daily=False)
    daily = classify(code=61, rain_amount=5.0, snow_amount=0.0, wind_speed=5.0, cloud_cover=50.0,
                      wind_threshold=25, daily=True)
    assert hourly.intensity == 1.0  # 5mm saturates the hourly nowcast scale
    assert daily.intensity < 1.0    # but is unremarkable as a daily total


def test_imperial_scale_is_not_the_metric_number():
    # 5 (unitless here) would saturate the metric mm scale but is absurd as inches
    metric = classify(code=61, rain_amount=5.0, snow_amount=0.0, wind_speed=5.0, cloud_cover=50.0,
                       wind_threshold=25, units="metric")
    imperial = classify(code=61, rain_amount=0.1, snow_amount=0.0, wind_speed=5.0, cloud_cover=50.0,
                         wind_threshold=25, units="imperial")
    assert metric.intensity == 1.0
    assert imperial.intensity < 1.0  # 0.1in is moderate, not saturating, on the imperial scale


def test_wind_overlay_threshold():
    below = classify(code=0, rain_amount=0.0, snow_amount=0.0, wind_speed=10.0, cloud_cover=0.0, wind_threshold=25)
    above = classify(code=0, rain_amount=0.0, snow_amount=0.0, wind_speed=30.0, cloud_cover=0.0, wind_threshold=25)
    assert below.wind_overlay is False
    assert above.wind_overlay is True


def test_unknown_code_falls_back_to_partly_cloudy():
    c = classify(code=12345, rain_amount=0.0, snow_amount=0.0, wind_speed=5.0, cloud_cover=40.0, wind_threshold=25)
    assert c.kind is IconKind.PARTLY_CLOUDY
