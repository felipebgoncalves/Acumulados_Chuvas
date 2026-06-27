def test_app_importa_sem_executar_streamlit():
    import app.main

    assert callable(app.main.run)
