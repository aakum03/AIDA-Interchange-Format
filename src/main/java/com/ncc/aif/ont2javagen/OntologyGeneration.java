package com.ncc.aif.ont2javagen;

import org.apache.jena.ontology.*;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.util.FileUtils;

import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.Charset;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.text.DateFormat;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.stream.Stream;

/**
 * Generates java resources from an ontology.  Directions for how to generate java files from this class can be found at
 * src/main/java/com/ncc/aif/ont2javagen/README.md
 */
public class OntologyGeneration {

    private OntModel ontModel;
    private static List<OWGClass> owgClassList = new ArrayList<>();


    private OntologyGeneration() {
        this.ontModel = this.createOntModel(false);
    }

    // Reads in ontology File
    private void addOntologyToGenerate(InputStream ontologyFile) {
        OntModel temp = this.createOntModel(false);
        temp.read(ontologyFile, "urn:x-base", FileUtils.langTurtle);

        this.ontModel.add(temp);
        this.classIterateOntology(temp);
    }

    // Iterates through new ontology model to obtain the list of classes
    private void classIterateOntology(OntModel tempont) {
        Iterator it = tempont.listClasses();

        while(it.hasNext()) {
            OntClass oc = (OntClass)it.next();
            if (!oc.isAnon()) {
                setResources(oc.getURI(), oc.getLocalName());
            }
        }

        Iterator itProperty = tempont.listAllOntProperties();

        while(itProperty.hasNext()) {
            OntProperty op = (OntProperty)itProperty.next();
            if (!op.isAnon()) {
                setResources(op.getURI(), op.getLocalName());
            }
        }
    }

    // Creates the ontology model based on the ontology argument
    private OntModel createOntModel(boolean processImports) {
        OntModelSpec s = new OntModelSpec(OntModelSpec.OWL_MEM);

        OntModel ontModel = ModelFactory.createOntologyModel(s,null);
        OntDocumentManager dm = ontModel.getDocumentManager();
        dm.setProcessImports(processImports);
        return ontModel;
    }

    private void setResources(String uri, String resourceName) {
        OWGClass owgClass = new OWGClass(uri, resourceName);
        owgClassList.add(owgClass);

    }

    /**
     * Will create java classes with resources from a given set of ontologies.
     * @param args String Array of locations to Ontologies that resources will be generated from.
     */
    public static void main(String[] args) {

        if (args.length == 0) {
            String root = "src/main/resources/com/ncc/aif/ontologies/";
            Stream.of(
                    "AidaDomainOntologiesCommon",
                    "EntityOntology",
                    "EventOntology",
                    "InterchangeOntology",
                    "LDCOntology",
                    "LDCOwlOntology",
                    "RelationOntology")
                .map(file -> root + file)
                .forEach(OntologyGeneration::writeJavaFile);
        } else {
            for (String arg : args) {
                writeJavaFile(arg);
            }
        }
    }

    // Writes the generated Java classes
    private static void writeJavaFile(String ontologyLocation) {
        try {
            OntologyGeneration ctx = new OntologyGeneration();
            ctx.addOntologyToGenerate(new FileInputStream(ontologyLocation));

            System.out.println("Generating for ontology located at " + ontologyLocation);
            OWGClass test = owgClassList.get(0);
            String classNameTest = test.uri;
            String variableClassName = classNameTest.substring(classNameTest.lastIndexOf('/') + 1, classNameTest.indexOf('#'));

            List<String> lines = owgMapperInfo(variableClassName);
            Path file = Paths.get("src/main/java/com/ncc/aif/" + variableClassName + ".java");
            Files.write(file, lines, Charset.forName("UTF-8"));
        } catch (IOException e) {
            System.err.println("Unable to process file " + ontologyLocation);
            e.printStackTrace();
        }
        owgClassList.clear();
    }

    // Writes the static variables for each ontology class
    private static List<String> owgMapperInfo(String variableClassName) {

        List<String> owgMapping = new ArrayList<>(owgMapperHeader());

        String className = "public final class " + variableClassName + " {";
        owgMapping.add(className);

        SortedSet<String> members = new TreeSet<>();
        for (OWGClass owgClass : owgClassList) {

            String name = owgClass.getName();

            if (name.contains(".") || name.contains("-")) {
                name = name.replace(".", "_");
                name = name.replace("-", "_");
            }

            members.add("    public static final Resource " + name + " = ResourceFactory.createResource(\"" + owgClass.getUri() + "\");");
        }
        owgMapping.addAll(members);

        String ending = "}";
        owgMapping.add(ending);

        return owgMapping;
    }

    // Writes the packages, imports and comments for the generated classes
    private static List<String> owgMapperHeader () {

        String lineEmpty = "";
        String lineOne = "package com.ncc.aif;";
        String lineThree = "import org.apache.jena.rdf.model.Resource;";
        String lineFour = "import org.apache.jena.rdf.model.ResourceFactory;";
        String lineWarningOne = "// WARNING. This is a Generated File.  Please do not edit.";
        String lineWarningTwo = "// This class contains Variables generated from Ontologies using the OntologyGeneration Class";
        String lineWarningThree = "// Please refer to the README at src/main/java/com/ncc/aif/ont2javagen for more information";

        DateFormat format = new SimpleDateFormat("MM/dd/yyy HH:mm:ss");
        Date date = Calendar.getInstance().getTime();

        String timeStamp = "// Last Generated On: " + format.format(date);

        List<String> headerStrings = new ArrayList<>();

        headerStrings.add(lineOne);
        headerStrings.add(lineEmpty);
        headerStrings.add(lineThree);
        headerStrings.add(lineFour);
        headerStrings.add(lineEmpty);
        headerStrings.add(lineWarningOne);
        headerStrings.add(lineWarningTwo);
        headerStrings.add(lineWarningThree);
        headerStrings.add(timeStamp);

        return headerStrings;
    }

    // Ontology classes that includes the name and uri of each class
    private class OWGClass {
        private String name;
        private String uri;

        private OWGClass (String uri, String name) {
            this.name = name;
            this.uri = uri;
        }

        public String getName() {
            return name;
        }

        public String getUri() {
            return uri;
        }
    }

}
