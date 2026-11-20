plugins {
    application
    id("com.github.johnrengelman.shadow") version "8.1.1"
}

/*
 * The desktop's NewPipeExtractor fallback.
 *
 * NewPipeExtractor is a JVM library. The desktop runs it in a small standalone
 * helper which returns a JSON stream manifest to the Python downloader. The
 * common desktop code remains responsible for stream selection, fetching,
 * progress reporting and cancellation.
 *
 * A fat jar and a jlink runtime keep the Java dependency self-contained in the
 * desktop package instead of asking users to install Java separately.
 */
repositories {
    mavenCentral()
    maven("https://jitpack.io")
}

dependencies {
    implementation("com.github.TeamNewPipe:NewPipeExtractor:v0.26.1")
    implementation("org.json:json:20240303")
}

application {
    mainClass.set("net.blueknight.newpipe.Main")
}

java {
    toolchain { languageVersion.set(JavaLanguageVersion.of(17)) }
}

tasks.shadowJar {
    archiveFileName.set("blueknight-newpipe.jar")
    // A duplicate META-INF entry from two dependencies is not worth failing a
    // build over, and the extractor pulls in several.
    mergeServiceFiles()
}
