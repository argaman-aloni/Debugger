import csv
import json
import os
import shutil
import subprocess
import sys

import itertools
import report
import utilsConf
import wekaMethods.ParseWekaOutput
import wekaMethods.articles
import wekaMethods.buildDB
import wekaMethods.commsSpaces
import wekaMethods.issuesExtract.github_import
import wekaMethods.issuesExtract.jira_import
import wekaMethods.issuesExtract.python_bugzilla
import wekaMethods.patchsBuild
import wekaMethods.wekaAccuracy
from utilsConf import Mkdirs, version_to_dir_name, mkOneDir
from run_mvn import AmirTracer, TestRunner
from sfl_diagnoser.Diagnoser.diagnoserUtils import write_planning_file, readPlanningFile
from experiments import ExperimentGenerator

"""
resources :
git
windows
xml-doclet-1.0.4-jar-with-dependencies.jar
checkStyle5.7
"""

"""
workingDir=C:\projs\antWorking
git=C:\projs\antC
vers=(ANT_13_B2,ANT_13_MAIN_MERGE4,ANT_MAIN_13_MERGE4)
"""

def OO_features_error_analyze(err):
    # get all corrupted java files in err
    lines=err.split("\n")
    wantedLines=[]
    i=0
    for l in lines:
        if "symbol:   variable " in l:
            wantedLines.append(lines[i-3])
        i=i+1
    knownP=["static import only from classes and interfaces","unmappable character for encoding"]
    knownP=[""]
    dontMatter=["does not exist","cannot find symbol"]
    wantedLines=wantedLines+[x for x in lines if ".java:" in x]
    lines=wantedLines
    for d in dontMatter:
        lines=[x for x in lines if d not   in x]
    ans=[]
    for p in knownP:
        ans=ans+[x.split(".java")[0]+".java" for x in lines if p in x]
    return ans


@utilsConf.marker_decorator(utilsConf.OO_OLD_FEATURES_MARKER)
def Extract_OO_features_OLD():
    for version in utilsConf.get_configuration().vers:
        verPath = os.path.join(utilsConf.get_configuration().versPath, version_to_dir_name(version))
        command = """cd /d  """ + utilsConf.to_short_path(verPath) + " & for /R .\\repo %f in (*.java) do (call javadoc -doclet com.github.markusbernhardt.xmldoclet.XmlDoclet -docletpath "+utilsConf.to_short_path(utilsConf.get_configuration().docletPath)+" -filename %~nxf.xml -private -d .\Jdoc2 %f >NUL 2>NUL)"
        os.system(command)
# GENERATE Jdoc


@utilsConf.marker_decorator(utilsConf.OO_FEATURES_MARKER)
def Extract_OO_features(versPath,vers,docletPath="..\..\\xml-doclet-1.0.4-jar-with-dependencies.jar"):
    for x in vers:
        verPath=os.path.join(versPath,x)
        outPath=os.path.join(verPath,"Jdoc")
        outPath=os.path.join(outPath,"javadoc.xml")
        err=""
        open(os.path.join(verPath,"JdocFunc.txt"),"wt").writelines([x for x in open(os.path.join(verPath,"javaFiles.txt"),"r").readlines()])
        run_commands = ["javadoc", "-doclet", "com.github.markusbernhardt.xmldoclet.XmlDoclet","-docletpath ", docletPath, "-private","-d",".\Jdoc","@JdocFunc.txt"]
        bads=[]
        if (not os.path.exists(outPath)):
            bads=bads+OO_features_error_analyze(err)
            open(os.path.join(verPath,"JdocFunc.txt"),"wb").writelines([x for x in open(os.path.join(verPath,"javaFiles.txt"),"r").readlines() if x not in bads ])
            proc = utilsConf.open_subprocess(run_commands, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True,cwd=utilsConf.to_short_path(verPath))
            (out, err) = proc.communicate()
            bads=bads+OO_features_error_analyze(err)
            open(os.path.join(verPath,"JdocFunc.txt"),"wb").writelines([x for x in open(os.path.join(verPath,"javaFiles.txt"),"r").readlines() if x not in bads ])
            proc = utilsConf.open_subprocess(run_commands, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True,cwd=utilsConf.to_short_path(verPath))
            (out, err) = proc.communicate()
# GENERATE Jdoc


#@utilsConf.marker_decorator(utilsConf.SOURCE_MONITOR_FEATURES_MARKER)
def SourceMonitorXml(workingDir, ver, sourceMonitorEXE):
    verDir=os.path.join(utilsConf.to_short_path(workingDir), "vers", ver)
    verREPO=os.path.join(verDir, "repo")
    verP=os.path.join(verDir, ver)
    xml="""
    <!--?xml version="1.0" encoding="UTF-8" ?-->
<sourcemonitor_commands>

   <write_log>true</write_log>

   <command>
       <project_file>verP.smp</project_file>
       <project_language>Java</project_language>
       <file_extensions>*.java</file_extensions>
       <source_directory>verREPO</source_directory>
       <include_subdirectories>true</include_subdirectories>
       <checkpoint_name>Baseline</checkpoint_name>

       <export>
           <export_file>verP.csv</export_file>
           <export_type>3 (Export project details in CSV)</export_type>
           <export_option>1 (do not use any of the options set in the Options dialog)</export_option>
       </export>
   </command>

   <command>
       <project_file>verP.smp</project_file>
       <project_language>Java</project_language>
       <file_extensions>*.java</file_extensions>
       <source_directory>verREPO</source_directory>
       <include_subdirectories>true</include_subdirectories>
       <checkpoint_name>Baseline</checkpoint_name>
       <export>
           <export_file>verP_methods.csv</export_file>
           <export_type>6 (Export method metrics in CSV)</export_type>
           <export_option>1 (do not use any of the options set in the Options dialog)</export_option>
       </export>
   </command>

</sourcemonitor_commands>""".replace("verP", verP).replace("verREPO", verREPO)
    xmlPath = os.path.join(verDir, "sourceMonitor.xml")
    with open(xmlPath, "wb") as f:
        f.write(xml)
    return [sourceMonitorEXE, "/C", xmlPath]


def blameExecute(path, pathRepo, version):
    for root, dirs, files in os.walk(pathRepo):
        for name in files:
            if not os.path.splitext(name)[1].endswith("java"):
                continue
            git_file_path = os.path.join(root, name).replace(pathRepo + "\\", "")
            blame_file_path = os.path.abspath(os.path.join(path, 'blame', name))
            blame_commands = ['git', 'blame', '--show-stats', '--score-debug', '-p', '--line-porcelain', '-l', version, git_file_path]
            proc = utilsConf.open_subprocess(blame_commands, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, cwd=utilsConf.to_short_path(pathRepo))
            (out, err) = proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError('blame subprocess failed. args: {0}. err is {1}'.format(str(blame_commands), err))
            with open(blame_file_path, "w") as f:
                f.writelines(out)
    run_commands = ["dir", "/b", "/s", "*.java"]
    proc = utilsConf.open_subprocess(run_commands, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, cwd=utilsConf.to_short_path(pathRepo))
    (out, err) = proc.communicate()
    with open(os.path.join(path, "javaFiles.txt"), "wb") as f:
        f.writelines(out)


@utilsConf.marker_decorator(utilsConf.COMPLEXITY_FEATURES_MARKER)
def Extract_complexity_features():
    processes = []
    for version_path, version_name, git_version in zip(utilsConf.get_configuration().vers_paths, utilsConf.get_configuration().vers_dirs,
                                                       utilsConf.get_configuration().vers):
        pathRepo=os.path.join(version_path,"repo")
        run_commands = SourceMonitorXml(utilsConf.get_configuration().workingDir, version_name, utilsConf.get_configuration().sourceMonitorEXE)
        proc = utilsConf.open_subprocess(run_commands, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        processes.append((proc, run_commands))
        run_commands = ["java", "-jar", utilsConf.get_configuration().checkStyle68, "-c", utilsConf.get_configuration().methodsNamesXML,"javaFile","-o","vers/checkAllMethodsData/"+version_name+".txt",pathRepo]
        proc = utilsConf.open_subprocess(run_commands, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, cwd=utilsConf.to_short_path(utilsConf.get_configuration().workingDir))
        processes.append((proc, run_commands))

        run_commands = ["java", "-jar", utilsConf.get_configuration().checkStyle57, "-c", utilsConf.get_configuration().allchecks,"-r",pathRepo,"-f","xml","-o","vers/checkAll/"+version_name+".xml"]
        proc = utilsConf.open_subprocess(run_commands, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, cwd=utilsConf.to_short_path(utilsConf.get_configuration().workingDir))
        processes.append((proc, run_commands))

        blameExecute(version_path, pathRepo, git_version)
    for proc, run_commands in processes:
        out, err = proc.communicate()
        if proc.returncode != 0:
            RuntimeWarning('subprocess execution failed. args are {0}. err is {1}'.format(str(run_commands), err))

# blame
#checkStyle
@utilsConf.marker_decorator(utilsConf.FEATURES_MARKER)
def featuresExtract():
    Extract_complexity_features()
    Extract_OO_features_OLD()
    wekaMethods.commsSpaces.create(utilsConf.get_configuration().vers_dirs, os.path.join(utilsConf.get_configuration().workingDir, "vers"))
    wekaMethods.patchsBuild.do_all()


def BuildWekaModel(weka, training, testing, namesCsv, outCsv, name, wekaJar):
    algorithm="weka.classifiers.trees.RandomForest -I 1000 -K 0 -S 1 -num-slots 1 "
    #os.system("cd /d  "+weka +" & java -Xmx2024m  -cp \"C:\\Program Files\\Weka-3-7\\weka.jar\" weka.Run " +algorithm+ " -x 10 -d .\\model.model -t "+training+" > training"+name+".txt")
    os.system("cd /d  "+ utilsConf.to_short_path(weka) +" & java -Xmx2024m  -cp "+utilsConf.to_short_path(wekaJar)+" weka.Run " +algorithm+ " -x 10 -d .\\model.model -t "+training+" > training"+name+".txt")
    # run_commands = ['java', '-Xmx2024m',  '-cp', wekaJar, 'weka.Run', algorithm, '-x', '10', '-d', '.\\model.model', 't']
    # proc = subprocess.Popen(run_commands, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, cwd=utilsConf.to_short_path(weka))
    # proc.communicate()
    algorithm="weka.classifiers.trees.RandomForest "
    os.system("cd /d  "+ utilsConf.to_short_path(weka) +" & java -Xmx2024m  -cp "+ utilsConf.to_short_path(wekaJar) +" weka.Run " +algorithm+ " -l .\\model.model -T "+testing+" -classifications \"weka.classifiers.evaluation.output.prediction.CSV -file testing"+name+".csv\" ")
    os.system("cd /d  "+ utilsConf.to_short_path(weka) +" & java -Xmx2024m  -cp "+ utilsConf.to_short_path(wekaJar) +" weka.Run " +algorithm+ " -l .\\model.model -T "+testing+" > testing"+name+".txt ")
    wekaCsv = os.path.join(utilsConf.to_short_path(weka), "testing"+name+".csv")
    wekaMethods.wekaAccuracy.priorsCreation(namesCsv, wekaCsv, outCsv, "")


def BuildMLFiles(outDir, buggedType, component):
    trainingFile=os.path.join(outDir,buggedType+"_training_"+component+".arff")
    testingFile=os.path.join(outDir,buggedType+"_testing_"+component+".arff")
    NamesFile=os.path.join(outDir,buggedType+"_names_"+component+".csv")
    outCsv=os.path.join(outDir,buggedType+"_out_"+component+".csv")
    return trainingFile, testingFile, NamesFile, outCsv


@utilsConf.marker_decorator(utilsConf.ML_MODELS_MARKER)
def createBuildMLModels():
    for buggedType in ["All", "Most"]:
        Bpath=os.path.join(utilsConf.get_configuration().workingDir, buggedType)
        mkOneDir(Bpath)
        FilesPath=os.path.join(Bpath, "Files")
        methodsPath=os.path.join(Bpath, "Methods")
        mkOneDir(FilesPath)
        mkOneDir(methodsPath)
        trainingFile,testingFile,NamesFile,Featuresnames,lensAttr=wekaMethods.articles.articlesAllpacks(FilesPath,
                                                                                                        utilsConf.get_configuration().gitPath, utilsConf.get_configuration().weka_path, utilsConf.get_configuration().vers, utilsConf.get_configuration().vers_dirs, buggedType, utilsConf.get_configuration().db_dir)
        trainingFile, testingFile, NamesFile, outCsv=BuildMLFiles(utilsConf.to_short_path(utilsConf.get_configuration().weka_path),buggedType,"files")
        BuildWekaModel(utilsConf.get_configuration().weka_path,trainingFile,testingFile,NamesFile,outCsv,"files_"+buggedType, utilsConf.get_configuration().wekaJar)
        # All_One_create.allFamilies(FilesPath,Featuresnames,lensAttr,trainingFile, testingFile,RemoveBat)
        trainingFile,testingFile,NamesFile,Featuresnames,lensAttr=wekaMethods.articles.articlesAllpacksMethods(methodsPath,
                                                                                                               utilsConf.get_configuration().gitPath, utilsConf.get_configuration().weka_path, utilsConf.get_configuration().vers, utilsConf.get_configuration().vers_dirs, buggedType, utilsConf.get_configuration().db_dir)
        trainingFile, testingFile, NamesFile, outCsv=BuildMLFiles(utilsConf.to_short_path(utilsConf.get_configuration().weka_path),buggedType,"methods")
        BuildWekaModel(utilsConf.get_configuration().weka_path,trainingFile,testingFile,NamesFile,outCsv,"methods_"+buggedType, utilsConf.get_configuration().wekaJar)
        # All_One_create.allFamilies(methodsPath,Featuresnames,lensAttr,trainingFile, testingFile,RemoveBat)


def mergeArffs(merge,arffFile,tempFile):
    os.system('java -Xmx2024m  -cp "C:\Program Files\Weka-3-7\weka.jar" weka.filters.unsupervised.attribute.RemoveByName -E hasBug -i '+ merge+' > '+ tempFile)
    os.system('java -Xmx2024m  -cp "C:\Program Files\Weka-3-7\weka.jar" weka.core.Instances merge '+ tempFile+' '+ arffFile+'  > '+ merge)


def indsFamilies(packsInds,Wanted):
    outpacksInds=[]
    for p in Wanted:
        lst = [packsInds[x] for x in p]
        outpacksInds.append(reduce(lambda x, y: x + y, lst))
    return outpacksInds


def merge_multiple_arff_file(path,outArff,tempFile,indices):
        shutil.copyfile(os.path.join(path,str(indices[0])),outArff)
        for ind in indices[1:]:
            arffFile=os.path.join(path,str(ind))
            mergeArffs(outArff,arffFile,tempFile)


def ArticleFeaturesMostFiles(workingDir,outArffTrain,outArffTest,tempFile,outCsv,wekaJar,indices):
    weka=os.path.join(workingDir,"weka")
    Bpath=os.path.join(workingDir,"Most")
    FilesPath=os.path.join(Bpath,"Files")
    FilesPath=os.path.join(FilesPath,"Fam_one")
    for train,name in zip([outArffTrain,outArffTest],["_Appended.arff","_Only.arff"]):
        shutil.copyfile(os.path.join(FilesPath,str(0)+name),train)
        for ind in indices[1:]:
            arffFile=os.path.join(FilesPath,str(ind)+name)
            mergeArffs(train,arffFile,tempFile)
    trainingFile,testingFile,NamesFile=BuildMLFiles(weka,"Most","files")
    BuildWekaModel(weka,outArffTrain,outArffTest,NamesFile,outCsv,"methods_"+"Most",wekaJar)

def append_families_indices(workingDir,wekaJar, fam_one_path, buggedType,component,indices):
    weka=os.path.join(workingDir,"weka")
    instance_name = component+"_"+buggedType
    outArffTrain = os.path.join(weka, instance_name + "_Appended.arff")
    outArffTest = os.path.join(weka, instance_name + "_Only.arff")
    tempFile= os.path.join(weka, instance_name + "_TMP.arff")
    for train,name in zip([outArffTrain,outArffTest],["_Appended.arff","_Only.arff"]):
        shutil.copyfile(os.path.join(fam_one_path,str(0)+name),train)
        for ind in indices[1:]:
            arffFile=os.path.join(fam_one_path,str(ind)+name)
            mergeArffs(train,arffFile,tempFile)
    trainingFile,testingFile,NamesFile, outCsv=BuildMLFiles(weka,buggedType,component)
    BuildWekaModel(weka,outArffTrain,outArffTest,NamesFile,outCsv,instance_name,wekaJar)

def weka_csv_to_readable_csv(weka_csv, prediction_csv):
    out_lines = [["component_name", "fault_probability"]]
    first = 0
    with open(weka_csv, "r") as f:
        reader = csv.reader(f)
        for l in reader:
            if (first == 0):
                first = 1
                continue
            component_name = l[0]
            probability = l[5].replace("*", "")
            out_lines.append([component_name, probability])
    with open(prediction_csv, "wb") as f:
        writer = csv.writer(f)
        writer.writerows(out_lines)


def add_to_packages(packages, path, probability, threshold=0.2):
    if float(probability) < threshold:
        return
    d = packages
    while len(path) != 1:
        name = path.pop()
        d.setdefault('_sub_packages', [])
        package = {'_name': name}
        d['_sub_packages'].append(package)
        d = package
    d.setdefault('_files', {})
    d['_files'][path[0]] = {'_probability': probability}


def calc_all_probabilities(package, reduce_function):
    if '_probability' not in package:
        sub_probabilities = [0.0]
        if '_files' in package:
            files_probabilities = map(lambda x: package['_files'][x]['_probability'], package['_files'].keys())
            sub_probabilities.extend(files_probabilities)
        if '_sub_packages' in package:
            sub_packages_probabilites = map(lambda x: calc_all_probabilities(x, reduce_function), package['_sub_packages'])
            sub_probabilities.extend(sub_packages_probabilites)
        package['_probability'] = reduce_function(sub_probabilities)
    return package['_probability']


def save_json_watchers(precidtion_csv):
    packges = {'_name': '_root', '_sub_packages': []}
    lines = []
    with open(precidtion_csv) as f:
        lines = list(csv.reader(f))[1:]
    map(lambda x: add_to_packages(packges, list(reversed(x[0].split(os.path.sep))), float(x[1])), lines)
    calc_all_probabilities(packges, max)
    with open(precidtion_csv.replace("csv", "json"), "wb") as f:
        f.write(json.dumps([packges]))


@utilsConf.marker_decorator(utilsConf.VERSION_TEST_MARKER)
def test_version_create():
    src = os.path.join(utilsConf.get_configuration().workingDir,"vers", utilsConf.get_configuration().vers_dirs[-2], "repo")
    dst = os.path.join(utilsConf.get_configuration().workingDir,"testedVer", "repo")
    if not os.path.exists(dst):
        shutil.copytree(src, dst)


def clean(versPath,LocalGitPath):
    shutil.rmtree(versPath, ignore_errors=True)
    shutil.rmtree(LocalGitPath, ignore_errors=True)


def download_bugs():
    bugsPath = utilsConf.get_configuration().bugsPath
    issue_tracker_url = utilsConf.get_configuration().issue_tracker_url
    issue_tracker_product = utilsConf.get_configuration().issue_tracker_product
    if utilsConf.get_configuration().issue_tracker == "bugzilla":
        wekaMethods.issuesExtract.python_bugzilla.write_bugs_csv(bugsPath, issue_tracker_url, issue_tracker_product)
    elif utilsConf.get_configuration().issue_tracker == "jira":
        wekaMethods.issuesExtract.jira_import.jiraIssues(bugsPath, issue_tracker_url, issue_tracker_product)
    elif utilsConf.get_configuration().issue_tracker == "github":
        wekaMethods.issuesExtract.github_import.GithubIssues(bugsPath, issue_tracker_url, issue_tracker_product)


def create_web_prediction_results():
    for buggedType, granularity in itertools.product(["All", "Most"], ["files", "methods"]):
        weka_csv = os.path.join(utilsConf.get_configuration().weka_path, "{buggedType}_out_{GRANULARITY}.csv".format(buggedType=buggedType, GRANULARITY=granularity))
        prediction_csv = os.path.join(utilsConf.get_configuration().web_prediction_results, "prediction_{buggedType}_{GRANULARITY}.csv".format(buggedType=buggedType, GRANULARITY=granularity))
        weka_csv_to_readable_csv(weka_csv, prediction_csv)
        save_json_watchers(prediction_csv)


@utilsConf.marker_decorator(utilsConf.LEARNER_PHASE_FILE)
def wrapperLearner():
    download_bugs()
    test_version_create()
    # NLP.commits.data_to_csv(os.path.join(workingDir, "NLP_data.csv"), gitPath, bugsPath)
    featuresExtract()
    wekaMethods.buildDB.buildOneTimeCommits()
    createBuildMLModels()
    create_web_prediction_results()


def load_prediction_file(prediction_path):
    predictions = {}
    with open(prediction_path) as f:
        lines = list(csv.reader(f))[1:]
        predictions = dict(
            map(lambda line: (line[0].replace(".java", "").replace(os.path.sep, ".").replace("").lower(), line[1]), lines))
    return predictions


@utilsConf.marker_decorator(utilsConf.EXECUTE_TESTS)
def executeTests():
    web_prediction_results = utilsConf.get_configuration().web_prediction_results
    matrix_path = os.path.join(web_prediction_results, "matrix_{0}_{1}.matrix")
    outcomes_path = os.path.join(web_prediction_results, "outcomes.json")
    diagnoses_path = os.path.join(web_prediction_results, "diagnosis_{0}_{1}.matrix")
    diagnoses_json_path = os.path.join(web_prediction_results, "diagnosis_{0}_{1}.json")
    tested_repo = utilsConf.to_short_path(os.path.join(utilsConf.get_configuration().workingDir, "testedVer", "repo"))
    test_runner = TestRunner(tested_repo, AmirTracer(tested_repo, utilsConf.get_configuration().amir_tracer, utilsConf.get_configuration().DebuggerTests))
    test_runner.run()
    tests = test_runner.get_tests()
    json_observations = map(lambda test: test_runner.observations[test].as_dict(), tests)
    with open(outcomes_path, "wb") as f:
        f.write(json.dumps(json_observations))
    for granularity in utilsConf.get_configuration().prediction_files:
        for bugged_type in utilsConf.get_configuration().prediction_files[granularity]:
            components_priors = get_components_probabilities(bugged_type, granularity, test_runner, tests)
            tests_details = map(
                lambda test_name: (test_name, list(set(test_runner.tracer.traces[test_name].get_trace(granularity)) & set(components_priors.keys())),
                                   test_runner.observations[test_name].get_observation()),
                tests)
            matrix = matrix_path.format(granularity, bugged_type)
            write_planning_file(matrix, [], filter(lambda test: len(test[1]) > 0, tests_details),
                                priors=components_priors)
            inst = readPlanningFile(matrix)
            inst.diagnose()
            named_diagnoses = sorted(inst.get_named_diagnoses(), key=lambda d: d.probability, reverse=True)
            with open(diagnoses_path.format(granularity, bugged_type), "wb") as diagnosis_file:
                diagnosis_file.writelines("\n".join(map(lambda d: repr(d), named_diagnoses)))
            with open(diagnoses_json_path.format(granularity, bugged_type), "wb") as diagnosis_json:
                diagnosis_json.writelines(json.dumps(map(lambda d: dict([('_name', d[0])] + d[1].as_dict().items()), enumerate(named_diagnoses))))
    return test_runner


def get_components_probabilities(bugged_type, granularity, test_runner, tests):
    predictions = {}
    with open(os.path.join(utilsConf.get_configuration().web_prediction_results, utilsConf.get_configuration().prediction_files[granularity][bugged_type])) as f:
        lines = list(csv.reader(f))[1:]
        predictions = dict(
            map(lambda line: (line[0].replace(".java", "").replace(os.path.sep, ".").lower().replace('$', '@'), line[1]), lines))
    components_priors = {}
    for component in set(
            reduce(list.__add__, map(lambda test_name: test_runner.tracer.traces[test_name].get_trace(granularity), tests), [])):
        for prediction in predictions:
            if prediction.endswith(component):
                components_priors[component] = max(float(predictions[prediction]), 0.01)
    return components_priors


def comprasionAll(confFile):
    vers, gitPath,bugsPath, workingDir = utilsConf.configure(confFile)
    for buggedType in ["All","Most"]:
        Bpath=os.path.join(workingDir,buggedType)
        FilesPath=os.path.join(Bpath,"Files")
        methodsPath=os.path.join(Bpath,"Methods")
        packs=["haelstead","g2","g3","methodsArticles","methodsAdded","hirarcy","fieldsArticles","fieldsAdded","constructorsArticles","constructorsAdded","lastProcess","simpleProcessArticles","simpleProcessAdded","bugs","sourceMonitor","checkStyle","blame"]#,"analyzeComms"]
        FeaturesClasses,Featuresnames=wekaMethods.articles.featuresPacksToClasses(packs)
        wekaMethods.ParseWekaOutput.comprasion(os.path.join(FilesPath,"Fam_one\\out"),os.path.join(FilesPath,"Fam_all\\out"), os.path.join(workingDir,buggedType+"_"+"Files")+".csv",Featuresnames)
        packs=["lastProcessMethods","simpleProcessArticlesMethods","simpleProcessAddedMethods","bugsMethods"]#,"analyzeComms"]
        FeaturesClasses,Featuresnames=wekaMethods.articles.featuresMethodsPacksToClasses(packs)
        wekaMethods.ParseWekaOutput.comprasion(os.path.join(methodsPath,"Fam_one\\out"),os.path.join(methodsPath,"Fam_all\\out"), os.path.join(workingDir,buggedType+"_"+"Methods")+".csv",Featuresnames)


def comprasionThreeFam(confFile):
    vers, gitPath,bugsPath, workingDir = utilsConf.configure(confFile)
    for buggedType in ["All","Most"]:
        Bpath=os.path.join(workingDir,buggedType)
        FilesPath=os.path.join(Bpath,"Files")
        methodsPath=os.path.join(Bpath,"Methods")
        packs=["Traditional" , "OO", "process" ,"Fault_History"]#,"analyzeComms"]
        wekaMethods.ParseWekaOutput.comprasion(os.path.join(FilesPath,"ThreeFam_Fam_one\\out"),os.path.join(FilesPath,"ThreeFam_Fam_all\\out"), os.path.join(workingDir,"ThreeFam_"+buggedType+"_"+"Files")+".csv",packs)
        packs=["Fault_History","process_version1","process_version2"]#,"analyzeComms"]
        wekaMethods.ParseWekaOutput.comprasion(os.path.join(methodsPath,"ThreeFam_Fam_one\\out"),os.path.join(methodsPath,"ThreeFam_Fam_all\\out"), os.path.join(workingDir,"ThreeFam_"+buggedType+"_"+"Methods")+".csv",packs)


def dictToList(dict,lst):
    ans=[]
    for l in lst:
        ans.append(dict[l])
    return ans

def comprasionTypes(confFile):
    vers, gitPath,bugsPath, workingDir = utilsConf.configure(confFile)
    learnerOutFile=os.path.join(workingDir,"learner.csv")
    wekaD=os.path.join(workingDir,"weka")
    keys=["TP Rate","FP Rate","Precision","Recall"," F-Measure","MCC","ROC Area","PRC Area"]
    titles=["type","class","TP Rate","FP Rate","Precision","Recall"," F-Measure","MCC","ROC Area","PRC Area"]
    classes=['bugged',"valid","both"]
    filesNames=["testingAll_files.txt", "testingAll_methods.txt", "testingMost_files.txt", "testingMost_methods.txt"]
    lines=[titles]
    for f in filesNames:
        file=os.path.join(wekaD,f)
        Exptype=f.replace(".txt","").replace(".testing","")
        parsedDict=wekaMethods.ParseWekaOutput.Parse(file)
        for d in parsedDict:
          lines.append([Exptype,d]+list(dictToList(parsedDict[d],keys)))
    f=open(learnerOutFile,"wb")
    writer=csv.writer(f)
    writer.writerows(lines)
    f.close()

def reportProjectData(confFile,globalConfFile):
#java -Xmx2024m  -cp "C:\Program Files\Weka-3-7\weka.jar" weka.core.Instances 13_Appended.arff
    vers, gitPath,bugsPath, workingDir = utilsConf.configure(confFile)
    versPath, dbadd= Mkdirs(workingDir, vers)
    LocalGitPath=os.path.join(workingDir,"repo")
    reportCsv=os.path.join(workingDir,"report.csv")
    lastVer=os.path.join(dbadd,vers[-1]+".db")
    testsDB=os.path.join(workingDir,"testsBugsMethods.db")
    report.report(reportCsv,LocalGitPath,lastVer,testsDB)


def create_experiment(test_runner, num_instances=50, tests_per_instance=50, bug_passing_probability=0.05):
    results_path = os.path.join(utilsConf.get_configuration().experiments, "{GRANULARITY}_{BUGGED_TYPE}")
    for granularity in utilsConf.get_configuration().prediction_files:
        for bugged_type in utilsConf.get_configuration().prediction_files[granularity]:
            eg = ExperimentGenerator(test_runner, granularity, bugged_type, num_instances, tests_per_instance, bug_passing_probability)
            results = eg.create_instances()
            with open(results_path.format(GRANULARITY=granularity, BUGGED_TYPE=bugged_type), 'wb') as f:
                f.write(json.dumps(results))


@utilsConf.marker_decorator(utilsConf.ALL_DONE_FILE)
def wrapperAll():
    wrapperLearner()
    create_experiment(executeTests())

if __name__ == '__main__':
    csv.field_size_limit(sys.maxint)
    utilsConf.configure(sys.argv[1])
    shutil.copyfile(sys.argv[1], utilsConf.get_configuration().configuration_path)
    if utilsConf.copy_from_cache() is not None:
        exit()
    if len(sys.argv) == 2:
        wrapperAll()
        utilsConf.export_to_cache()
    elif sys.argv[2] =="learn":
        wrapperLearner()