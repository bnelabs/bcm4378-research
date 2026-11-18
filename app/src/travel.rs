use crate::network::{Band, country_code};
use std::collections::BTreeMap;
use std::sync::OnceLock;

type CountryPlans = BTreeMap<String, BTreeMap<String, BTreeMap<u16, Vec<u16>>>>;

fn plans() -> &'static CountryPlans {
    static PLANS: OnceLock<CountryPlans> = OnceLock::new();
    PLANS.get_or_init(|| {
        serde_json::from_str(include_str!("../Resources/channel-plans.json"))
            .expect("the packaged channel table must be valid")
    })
}

pub fn knows(text: &str) -> bool {
    country_code(text).is_some_and(|country| plans().contains_key(&country))
}

pub struct Comparison {
    pub first: String,
    pub second: String,
    pub common: Vec<u16>,
    pub first_only: Vec<u16>,
    pub second_only: Vec<u16>,
}

pub fn compare(first: &str, second: &str, band: Band, width: u16) -> Option<Comparison> {
    let first = country_code(first)?;
    let second = country_code(second)?;
    let rows = |country: &str| -> Option<&[u16]> {
        let bands = plans().get(country)?;
        Some(
            bands
                .get(band.label())
                .and_then(|widths| widths.get(&width))
                .map_or(&[], Vec::as_slice),
        )
    };
    let left = rows(&first)?;
    let right = rows(&second)?;
    Some(Comparison {
        common: left
            .iter()
            .copied()
            .filter(|channel| right.contains(channel))
            .collect(),
        first_only: left
            .iter()
            .copied()
            .filter(|channel| !right.contains(channel))
            .collect(),
        second_only: right
            .iter()
            .copied()
            .filter(|channel| !left.contains(channel))
            .collect(),
        first,
        second,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn local_plans_match_the_verified_band_edges() {
        assert_eq!(plans().len(), 222);
        let plan = compare("tr", " us ", Band::Five, 20).unwrap();
        assert!(plan.common.contains(&40));
        assert!(plan.second_only.contains(&144));
        assert!(compare("TR", "../../../", Band::Five, 20).is_none());
        assert!(
            compare("TR", "US", Band::Six, 20)
                .unwrap()
                .common
                .is_empty()
        );
    }
}
