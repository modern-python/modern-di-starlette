def test_public_surface_importable() -> None:
    import modern_di_starlette  # noqa: PLC0415

    assert modern_di_starlette.__all__ == []
