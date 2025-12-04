import pandas as pd

COORDENADAS_ESPIRITO_SANTO = {
    "AFONSO CLÁUDIO": (-20.0761, -41.1252),
    "ÁGUIA BRANCA": (-18.9964, -40.7355),
    "ÁGUA DOCE DO NORTE": (-18.5533, -40.9854),
    "ALEGRE": (-20.758, -41.5376),
    "ALFREDO CHAVES": (-20.6368, -40.7541),
    "ALTO RIO NOVO": (-19.0611, -41.0208),
    "ANCHIETA": (-20.7956, -40.6525),
    "APIACÁ": (-21.1524, -41.5692),
    "ARACRUZ": (-19.8266, -40.2767),
    "ATÍLIO VIVACQUA": (-20.9133, -41.1865),
    "BAIXO GUANDU": (-19.5212, -41.0036),
    "BARRA DE SÃO FRANCISCO": (-18.7536, -40.8939),
    "BOA ESPERANÇA": (-18.6023, -40.3002),
    "BOM JESUS DO NORTE": (-21.1188, -41.679),
    "BREJETUBA": (-20.4656, -41.2954),
    "CACHOEIRO DE ITAPEMIRIM": (-20.8462, -41.1122),
    "CARIACICA": (-20.2632, -40.4179),
    "CASTELO": (-20.6054, -41.1982),
    "COLATINA": (-19.5225, -40.6275),
    "CONCEIÇÃO DA BARRA": (-18.5968, -39.7341),
    "CONCEIÇÃO DO CASTELO": (-20.3668, -41.2413),
    "DIVINO DE SÃO LOURENÇO": (-20.63, -41.6949),
    "DOMINGOS MARTINS": (-20.3623, -40.6593),
    "DORES DO RIO PRETO": (-20.6936, -41.8407),
    "ECOPORANGA": (-18.3739, -40.8363),
    "FUNDÃO": (-19.9367, -40.3949),
    "GOVERNADOR LINDENBERG": (-19.2519, -40.4608),
    "GUAÇUÍ": (-20.7704, -41.6741),
    "GUARAPARI": (-20.6772, -40.5099),
    "IBATIBA": (-20.2344, -41.5085),
    "IBIRAÇU": (-19.8361, -40.3731),
    "IBITIRAMA": (-20.3591, -41.6768),
    "ICONHA": (-20.7913, -40.8132),
    "IRUPI": (-20.3531, -41.646),
    "ITAGUAÇU": (-19.8027, -40.8641),
    "ITAPEMIRIM": (-21.0267, -40.8326),
    "ITARANA": (-19.8631, -40.8751),
    "IÚNA": (-20.3556, -41.5323),
    "JAGUARÉ": (-18.907, -40.075),
    "JERÔNIMO MONTEIRO": (-20.7993, -41.3942),
    "JOÃO NEIVA": (-19.7579, -40.3869),
    "LARANJA DA TERRA": (-19.9007, -41.0436),
    "LINHARES": (-19.3946, -40.0727),
    "MANTENÓPOLIS": (-18.8594, -41.1236),
    "MARATAÍZES": (-21.0374, -40.8316),
    "MARECHAL FLORIANO": (-20.4157, -40.6715),
    "MARILÂNDIA": (-19.4118, -40.5413),
    "MIMOSO DO SUL": (-21.0661, -41.3679),
    "MONTANHA": (-18.1302, -40.3661),
    "MUCURICI": (-18.0973, -40.526),
    "MUNIZ FREIRE": (-20.4678, -41.4153),
    "MUQUI": (-20.9491, -41.3462),
    "NOVA VENÉCIA": (-18.7114, -40.399),
    "PANCAS": (-19.2283, -40.8535),
    "PEDRO CANÁRIO": (-18.2986, -39.9579),
    "PINHEIROS": (-18.4112, -40.0987),
    "PIÚMA": (-20.8352, -40.7283),
    "PONTO BELO": (-18.1258, -40.5456),
    "PRESIDENTE KENNEDY": (-21.0968, -41.0315),
    "RIO BANANAL": (-19.2709, -40.3364),
    "RIO NOVO DO SUL": (-20.8621, -40.9385),
    "SANTA LEOPOLDINA": (-20.0997, -40.5281),
    "SANTA MARIA DE JETIBÁ": (-20.0179, -40.7576),
    "SANTA TERESA": (-19.9312, -40.5962),
    "SÃO DOMINGOS DO NORTE": (-19.1455, -40.6287),
    "SÃO GABRIEL DA PALHA": (-19.015, -40.5364),
    "SÃO JOSÉ DO CALÇADO": (-21.0265, -41.6445),
    "SÃO MATEUS": (-18.7196, -39.8569),
    "SÃO ROQUE DO CANAÃ": (-19.7449, -40.6529),
    "SERRA": (-20.1211, -40.3074),
    "SOORETAMA": (-19.1893, -40.0755),
    "VARGEM ALTA": (-20.6697, -41.0172),
    "VENDA NOVA DO IMIGRANTE": (-20.3504, -41.1351),
    "VIANA": (-20.3833, -40.4935),
    "VILA PAVÃO": (-18.6096, -40.6094),
    "VILA VALÉRIO": (-18.9952, -40.3846),
    "VILA VELHA": (-20.3386, -40.2925),
    "VITÓRIA": (-20.3155, -40.3128)
}


def municipios_lat_lon_acumulados(df: pd.DataFrame) -> dict:

    # dicionário para armazenar as coordenadas geográficas dos municípios
    coordenadas_municipios_chuva = {}

    # Verificar quais municípios do dicionário de coordenadas estão no DataFrame
    for municipio, coordenadas in COORDENADAS_ESPIRITO_SANTO.items():
        if municipio in df['Município'].values:
            mm_value = df.loc[df['Município'] == municipio, 'Prec_mm'].values[0]
            coordenadas_municipios_chuva[municipio] = coordenadas, mm_value

    return coordenadas_municipios_chuva


def get_municipio_coords(municipio: str) -> dict:
    """
    Recebe o nome de um município do Espírito Santo e retorna sua latitude e longitude.
    """
    coordenadas = COORDENADAS_ESPIRITO_SANTO.get(municipio)
    
    return {municipio: coordenadas}