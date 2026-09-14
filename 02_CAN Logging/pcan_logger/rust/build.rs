// build.rs -- tell cargo where to find the PCAN-Basic library.
//
//   PCAN_LIB_DIR   directory containing libpcanbasic.so (Linux) or PCANBasic.lib/.dll (Windows)
//                  Leave unset if the library is on the default search path
//                  (e.g. /usr/lib after installing PCAN-Basic for Linux).
//
// The library name itself is chosen in src/main.rs with #[link(name = ...)].
fn main() {
    println!("cargo:rerun-if-env-changed=PCAN_LIB_DIR");
    if let Ok(dir) = std::env::var("PCAN_LIB_DIR") {
        println!("cargo:rustc-link-search=native={}", dir);
        // On Linux also bake the directory into the binary's rpath so it runs without LD_LIBRARY_PATH.
        #[cfg(not(target_os = "windows"))]
        println!("cargo:rustc-link-arg=-Wl,-rpath,{}", dir);
    }
}
