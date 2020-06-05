// Source adopted from
// https://github.com/tildeio/helix-website/blob/master/crates/word_count/src/lib.rs

use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use rayon::prelude::*;

/// Searches for the word, parallelized by rayon
#[pyfunction]
fn search(py: Python<'_>, contents: &str, search: String) -> PyResult<usize> {
    let count = py.allow_threads(move || {
        contents
            .par_lines()
            .map(|line| count_line(line, &search))
            .sum()
    });
    Ok(count)
}

/// Searches for a word in a classic sequential fashion
#[pyfunction]
fn search_sequential(contents: &str, needle: String) -> PyResult<usize> {
    let result = contents.lines().map(|line| count_line(line, &needle)).sum();
    Ok(result)
}

fn matches(word: &str, needle: &str) -> bool {
    let mut needle = needle.chars();
    for ch in word.chars().skip_while(|ch| !ch.is_alphabetic()) {
        match needle.next() {
            None => {
                return !ch.is_alphabetic();
            }
            Some(expect) => {
                if ch.to_lowercase().next() != Some(expect) {
                    return false;
                }
            }
        }
    }
    return needle.next().is_none();
}

/// Count the occurences of needle in line, case insensitive
#[pyfunction]
fn count_line(line: &str, needle: &str) -> usize {
    let mut total = 0;
    for word in line.split(' ') {
        if matches(word, needle) {
            total += 1;
        }
    }
    total
}

#[pymodule]
fn word_count(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_wrapped(wrap_pyfunction!(count_line))?;
    m.add_wrapped(wrap_pyfunction!(search))?;
    m.add_wrapped(wrap_pyfunction!(search_sequential))?;

    Ok(())
}
