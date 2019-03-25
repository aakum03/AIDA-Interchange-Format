# AIDA Interchange Format (AIF)

This repository contains resources to support the AIDA Interchange Format (AIF).  It consists of:

*    a formal representation of the format in terms of an OWL ontology in `src/main/resources/com/ncc/aif/ontologies/InterchangeOntology`.
     This ontology can be validated using the SHACL constraints file in
     `src/main/resources/com/ncc/aif/aida_ontology.shacl`.

*    utilities to make it easier to work with this format.  Java utilities are in
     `src/main/java/com/ncc/aif/AIFUtils.java`. A Kotlin version of the utilities are in
	 `src/main/java/edu/isi/gaia/AIFUtils.kt`.  Either of these can be used by adding a Maven dependency on
     `com.ncc:aida-interchange:1.0.0-SNAPSHOT`.  A Python translation of these utilities
     is in `python/aida_interchange/aifutils.py`.
	 
	 * The Java version remains in active development.  The Kotlin version will be deprecated at a later date.
	 Specific instructions for migrating from the Kotlin to the Java version is provided in the FAQ (`FAQ.md`).

*    examples of how to use AIF. These are given in Java in the unit tests under
     `src/test/java/com/ncc/aif/ExamplesAndValidationTests`.  A Python
     translation of these examples is in `python/tests/Examples.py`.  If you run either set of
     examples, the corresponding Turtle output will be dumped.
	 
	 * Validation tests that use the Kotlin implementation of AIF are located at
	 `src/test/java/edu/isi/gaia/ExamplesAndValidationTests`.
	 * Validation tools for the Python output is currently in progress.

*    code to translate from the TAC KBP Coldstart++ KB format into this format.
     `src/main/java/edu/isi/gaia/ColdStart2AidaInterchange.kt`.  ColdStart is only available
	 in Kotlin and is unsupported.

*    code to translate a simple format for entity and event mentions in images to AIF:
     `src/main/java/edu/isi/gaia/ImagesToAIF.kt`  This is currently only available in Kotlin.

We recommend using Turtle format for AIF when working with single document files (for
readability) but N-Triples for working with large KBs (for speed).

# Installation

* To install the Java and Kotlin/JVM code, do `mvn install` from the root of this repository using Apache Maven.
Repeat this if you pull an updated version of the code. You can run the tests,
which should output the examples, by doing `mvn test`.
* The Python code is not currently set up for installation; just add `AIDA-Interchange-Format/python` to your `PYTHONPATH`.

# Using the AIF Library

To use the library in Java, include the library generated by the
installation above into your build script or tool.  For gradle, for
example, include the following in the dependencies in your `build.gradle` file:

`dependencies {
    compile 'com.ncc:aida-interchange:1.0-SNAPSHOT'
}`

In your code, import classes from the `com.ncc.aif` or `edu.isi.gaia` packages to use the Java or Kotlin version, respectively.
Then, create a model, add entities, relations, and events to the
model, and then write the model out.

The file `src/test/java/com/ncc/aif/ExamplesAndValidationTests.java`
has a series of examples showing how to add things to the model.  The
`src/text/java/com/ncc/aif/ScalingTest.java` file has examples of how
to write the model out.

The file `src/test/java/edu/isi/gaia/ExamplesAndValidationTests.java`
has similar examples that use the Kotlin version.

# The AIF Validator
The AIF validator is an extension of the validator written by Ryan Gabbard (USC ISI)
and converted to Java by Next Century.  This version of the validator accepts multiple
ontology files, can validate against NIST requirements (restricted AIF), and can
validate N files or all files in a specified directory.

### Running the AIF validator
To run the validator from the command line, run `target/appassembler/bin/validateAIF`
with a series of command-line arguments (in any order) honoring the following usage:  <br>
Usage:  <br>
`validateAIF { --ldc | --program | --ont FILE ...} [--nist] [--nist-ta3] [-h | --help] {-f FILE ... | -d DIRNAME}`  <br>
Options:  <br>
`--ldc` validate against the LDC ontology  <br>
`--program` validate against the program ontology  <br>
`--ont FILE ...` validate against the OWL-formatted ontolog(ies) at the specified filename(s)  <br>
`--nist` validate against the NIST restrictions  <br>
`--nist-ta3` validate against the NIST hypothesis restrictions (implies --nist) <br>
`-h, --help` This help and usage text  <br>
`-f FILE ...` validate the specified file(s) with a .ttl suffix  <br>
`-d DIRNAME` validate all .ttl files in the specified directory  <br>
Either a file (-f) or a directory (-d) must be specified (but not both).  <br>
Exactly one of --ldc, --program, or --ont must be specified.  <br>
Ontology files can be found in `src/main/resources/com/ncc/aif/ontologies`:
- LDC (LO): `SeedlingOntology`
- Program (AO): `EntityOntology`, `EventOntology`, `RelationOntology`

### Validator return values
Return values from the command-line validator are as follows:
* `0 (Success)`.  There were no validation (or any other) errors.
* `1 (Validation Error)`.	All specified files were validated but at least one failed validation.
* `2 (Usage Error)`.  There was a problem interpreting command-line arguments.  No validation was performed.
* `3 (File Error)`.  There was a problem reading one or more files or directories.  Validation may have been performed on a subset of specified KBs.  If there is an error loading any ontologies or SHACL files, then no validation is performed.

### Running the validator in code
To run the validator programmatically in Java code, first use one of the public `ValidateAIF.createXXX()`
methods to create a validator object, then call one of the public `validateKB()` methods.
`createForLDCOntology()` and `createForProgramOntology()` are convenience wrappers for `create()`, which
is flexible enough to take a Set of ontologies.  All creation methods accept a flag for validating
against restricted AIF.  See the JavaDocs.

Note: the original `ValidateAIF.createForDomainOntologySource()` method remains for backward compatibility.

### Differences from the legacy validator
The AIF Validator bears certain important differences from the previous version of
the validator (still currently available-- see *Running the legacy validator* below).
* The validator no longer accepts a parameter file to specify, essentially,
its program arguments.  Instead, it takes all arguments as command-line options.
* The validator no longer ensures that confidences are between 0 and 1.
* The validator will now only validate files with the `.ttl` extension.
* The validator returns a variety of return codes (see above).

### Running the legacy validator (Kotlin only)

To run the legacy validator from the command line, run `target/appassembler/bin/validateAIF-kotlin` with a single argument, a parameter
file. The parameter file should have keys and values separated by `:`. It should have either the
parameter `kbToValidate` pointing to the single Turtle format KB to validate, or it should have
`kbsToValidate` pointing to a file listing the paths of the Turtle format KBs to validate.
Additionally, it must have a parameter `domainOntology` pointing to the OWL file for the domain
ontology to validate against.  Beware that validating large KBs can take a long time. There is
a sample of a validator param file in `sample_params/validate.common_corpus.single.params`.

# Running the Ontology Resource Generator

To generate the resource variables from a particular ontology file, please refer to 
the README located at `src/main/java/com/ncc/aif/ont2javagen/README.md`.

# Running the ColdStart -> AIF Converter (Kotlin only)

To convert a ColdStart KB, run `target/appassembler/bin/coldstart2AidaInterchange`. It takes a
single argument, a key-value parameter file where keys and values are separated by `:`.  There
are four parameters which are always required:
* `inputKBFile`: the path to the ColdStart KB to convert
* `baseUri`: the URI path to use as the base for generated assertions URIs, entity URIs, etc.  For
    example `http://www.isi.edu/aida`
* `systemUri`: a URI path to identify the system which generated the ColdStart output. For
    example `http://www.rpi.edu/tinkerbell`
* `mode`: must be `FULL` or `SHATTER`, as explained below.
* `ontology`: path of the file describing the ontology to use in AIF. For the M9 Seedling
    point to `src/main/resources/edu/isi/gaia/SeedlingOntology`.
* `relationArgsFile`: In ColdStart, you assert a relation between two entities, with the one
    on the left being the subject and the one on the right being the object.  In AIF relations
    are represented more like events and the relation arguments have relation-specific names
    instead of generic names like "subject" and "object". Because of this, you need a file 
    which specifies these names for each relation. For the M9 Seedling ontology, you can use
    `src/main/resources/edu/isi/gaia/seedling_relation_args.csv`

If `mode` is `FULL`, then the entire ColdStartKB is converted into a single AIF RDF file in
n-triples format (n-triples is used for greater I/O speed).  The following parameters then
 apply:
 * `outputAIFFile` will specify the path to write this file to.
 * cross document coreference information present in the ColdStartKB can be discarded by setting
     the optional parameter `breakCrossDocCoref` to `true` (default `false`).
* The optional `restrictConfidencesToJustifications` parameter (default `false`) controls whether
   confidence values are attached directly to the relevant entity/relation/event/sentiment
   assertion or only to their justifications.  The former is how it should be in TA2/TA3, but the
   latter for messages from TA1 to TA2.  Note this is somewhat imperfect because ColdStart
   lacks justifications for type and link assertions, so for these confidence information will
   simply be missing when restricting to justifications.

If `mode` is `SHATTER`, the data related to each document in the ColdStart KB is written to a
separate AIF file in Turtle format.  In this case, the only other parameter is the directory
to write the output to (`outputAIFDirectory`).  The values of `breakCrossDocCoref`,
`useClustersForCoref`, and `attachConfidencesToJustifications` are fixed at `true`, `false`,
and `true`, respectively.

The following optional parameters are available in both modes:
* `useClustersForCoref` parameter (default `false`) specifies whether
      to use the "clusters" provided by the AIF format for representing coreference.  While in AIDA
      there can be uncertainty about coreference, making these clusters useful, in ColdStart
      coreference decisions were always "hard".  We provide the user with the option of whether to
      encode these coref decisions in the way they would be encoded in AIDA if there were any
      uncertainty so that users can test these data structures.

There are sample shatter and single KB param files under `sample_params/translate.*`

# Additional Information about Individual Ontologies

There is another README located at `src/main/resources/com/ncc/aif/ontologies/README.md` that gives a description about each of the ontology files currently available in AIF.

# `maxConfidence`

There is an example program showing how to consume AIF data in `edu.isi.gaia.MaxConfidenceEstimator`.
This is currently only available in Kotlin.

# `imagesToAif`

There is an example program/utility for converting a simple tab-separated format for images to AIF.
See class comment on `src/main/java/edu/isi/gaia/ImagesToAIF.kt` for details. You can run this
program by running `target/appassembler/bin/images2Aif`.  This is currently only available in Kotlin.

# Developing

If you need to edit either the Java or Kotlin code:
 1. Install IntelliJ IDEA.
 2. "Import Project from Existing Sources"
 3. Choose the `pom.xml` for this repository and accept all defaults.

You should now be ready to go.

# FAQ

Please see `FAQ.md` for frequently asked questions.

# Contact

AIF was designed by Ryan Gabbard (gabbard@isi.edu) and Pedro Szekely
(pszekeley@isi.edu) of USC ISI.  Gabbard also wrote the initial
implementations of the associated tools.  The tools are now supported
and extended by Eddie Curley (eddie.curley@nextcentury.com), Bao Pham
(bao.pham@nextcentury.com), Clark Dorman (clark.dorman@nextcentury.com),
and Darren Gemoets (darren.gemoets@nextcentury.com) of Next Century.

The open repository will support an open NIST evaluation. For
questions related to this evaluation, please contact Hoa Dang
(hoa.dang@nist.gov).

# Legal Stuff

This material is based on research sponsored by DARPA under agreement
number FA8750-18- 2-0014 and FA875018C0010-HR0011730814.  The
U.S. Government is authorized to reproduce and distribute reprints for
Governmental purposes notwithstanding any copyright notation thereon.

The views and conclusions contained herein are those of the authors
and should not be interpreted as necessarily representing the official
policies or endorsements, either expressed or implied, of DARPA or the
U.S. Government.

The AIF repository has been approved by DARPA for public release under
Distribution Statement "A" (Approved for Public Release, Distribution
Unlimited).
