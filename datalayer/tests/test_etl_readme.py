from pathlib import Path

from sieej_datalayer.config import Settings
from sieej_datalayer.etl_readme import leer_documentos, parsear_readme
from sieej_datalayer.models import EstadoFuente

ETL = Path(__file__).parent / "fixtures" / "etl"


def test_el_readme_se_parte_en_la_ficha_del_pipeline():
    md = (ETL / "core/pipelines/denue/README.md").read_text(encoding="utf-8")
    doc = parsear_readme("denue", md)
    assert doc.titulo == "DENUE"
    assert doc.descripcion[0].startswith("Pipeline ETL del **Directorio")
    assert doc.avisos == [
        "**Las coordenadas son las declaradas por el INEGI.** No se corrigen en el pipeline."
    ]
    assert [(c.etiqueta, c.valor) for c in doc.caracteristicas][0] == (
        "Primer periodo disponible",
        "`2010-07`",
    )
    assert doc.fuente_general == "https://www.inegi.org.mx/app/descarga/?ti=6"
    assert doc.descargas[0].variable == "DENUE_URL"
    assert doc.descripcion_tablas == {
        "stg_denue": "Una fila por unidad económica activa en Jalisco.",
        "cat_sector": "Sectores SCIAN",
    }
    assert doc.alcance_vistas == {"v_establecimientos": "Establecimientos de Jalisco con su sector"}
    assert [v.etiqueta for v in doc.variables] == ["DENUE_URL"]


def test_la_carpeta_en_plural_se_nombra_como_la_base():
    fuente, docs = leer_documentos(Settings(_env_file=None, etl_repo_dir=ETL))
    assert fuente.estado is EstadoFuente.OK
    assert set(docs) == {"denue", "conapo", "censo_economico"}
    assert docs["censo_economico"].carpeta == "censos_economicos"


def test_un_clon_sin_readme_cuenta_como_caida(tmp_path):
    fuente, docs = leer_documentos(Settings(_env_file=None, etl_repo_dir=tmp_path))
    assert fuente.estado is EstadoFuente.CAIDA
    assert docs == {}


def test_sin_clon_configurado_no_se_consulta():
    fuente, docs = leer_documentos(Settings(_env_file=None))
    assert fuente.estado is EstadoFuente.SIN_CONFIGURAR
