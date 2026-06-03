from agentTaxonomy.matrix import expand_matrix


def test_default_matrix_expansion_count() -> None:
    cells = expand_matrix(
        matrix_path="benchmark/configs/experiment_matrix.yaml",
        models_path="benchmark/configs/models.yaml",
    )
    assert len(cells) == 30 * 3 * 12
    assert cells[0].prompt_level in {"low_specificity", "medium_specificity", "high_specificity"}
