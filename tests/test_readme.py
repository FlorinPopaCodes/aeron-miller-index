from pathlib import Path

from src.main import generate_readme
from src.models import Product


def test_generate_readme_uses_latest_stats(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    csv_path = data_dir / "sample.csv"
    csv_path.write_text(
        "\n".join(
            [
                "date,count,min,max,mean,median",
                "2025-01-01,1,100,100,100,100",
                "2025-01-02,2,100,200,150,150",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    products = [Product(slug="sample", name="Sample", query="sample")]
    readme_file = tmp_path / "README.md"
    base_url = "https://example.com"

    generate_readme(products, data_dir, readme_file, base_url)

    content = readme_file.read_text(encoding="utf-8")
    assert "Sample" in content
    assert "| Listings | 2 |" in content
    assert "| Last Update | 2025-01-02 |" in content
    assert f"{base_url}/images/overview.png" in content
    assert f"{base_url}/images/sample_dashboard.png" in content
