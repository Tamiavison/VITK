import itk
import vtk
from vtk.util import numpy_support
import numpy as np

print("Début de l'exécutable.")
#chargement des scans
scan1_path = 'Data/case6_gre1.nrrd'
scan2_path = 'Data/case6_gre2.nrrd'

scan1 = itk.imread(scan1_path, itk.F)
scan2 = itk.imread(scan2_path, itk.F)

print("Les scans ont été chargés avec succès.")
print("Début du réalignement")

def realign(fixed_image, moving_image):
    Dimension = 3
    PixelType = itk.F

    # définir les types de transformation, optimiseur et métrique
    FixedImageType = itk.Image[PixelType, Dimension]
    MovingImageType = itk.Image[PixelType, Dimension]
    TransformType = itk.TranslationTransform[itk.D, Dimension]
    OptimizerType = itk.RegularStepGradientDescentOptimizerv4[itk.D]
    MetricType = itk.MattesMutualInformationImageToImageMetricv4[FixedImageType, MovingImageType]
    RegistrationType = itk.ImageRegistrationMethodv4[FixedImageType, MovingImageType]

    # Initialiser la transformation
    initial_transform = TransformType.New()
    initial_transform.SetIdentity()

    # Créer les composants de recalage
    optimizer = OptimizerType.New()
    optimizer.SetLearningRate(1.0)
    optimizer.SetMinimumStepLength(0.001)
    optimizer.SetNumberOfIterations(300)

    metric = MetricType.New()
    metric.SetNumberOfHistogramBins(50)

    registration = RegistrationType.New()
    registration.SetFixedImage(fixed_image)
    registration.SetMovingImage(moving_image)
    registration.SetInitialTransform(initial_transform)
    registration.SetMetric(metric)
    registration.SetOptimizer(optimizer)
    registration.SetNumberOfLevels(1)

    registration.Update()

    # Appliquer la transformation à l'image déplacée
    resample_filter = itk.ResampleImageFilter.New(Input=moving_image, Transform=registration.GetTransform(), UseReferenceImage=True, ReferenceImage=fixed_image, DefaultPixelValue=0)
    resample_filter.Update()
    realign_scan2 = resample_filter.GetOutput()

    return realign_scan2

realign_scan2 = realign(scan1, scan2)

print("Réalignement terminé.")
print("Début du prétraitement.")

def preprocess_image(image):
    smooth = itk.CurvatureFlowImageFilter.New(Input=image, TimeStep=0.125, NumberOfIterations=5)
    smooth.Update()
    
    rescale = itk.RescaleIntensityImageFilter.New(Input=smooth.GetOutput(), OutputMinimum=0, OutputMaximum=255)
    rescale.Update()
    
    return rescale.GetOutput()

preprocessed_scan1 = preprocess_image(scan1)
preprocessed_scan2 = preprocess_image(realign_scan2)

print("Prétraitement terminé.")
print("Début de la segmentation.")

# Fonction pour segmenter la tumeur en utilisant ConnectedThresholdImageFilter
def segment_tumor(image, seed_point, lower_threshold, upper_threshold):
    seg = itk.ConnectedThresholdImageFilter.New(Input=image)
    seg.SetLower(lower_threshold)
    seg.SetUpper(upper_threshold)
    seg.AddSeed(seed_point)
    seg.Update()
    return seg.GetOutput()

# seed points
seed_point1 = (125, 65, 82)
seed_point2 = (125, 65, 82)

upper_threshold = 1000

tumor1 = segment_tumor(preprocessed_scan1, seed_point1, 76, upper_threshold)
tumor2 = segment_tumor(preprocessed_scan2, seed_point2, 94, upper_threshold)

print("Segmentation des tumeurs terminée.")

def calculate_volume(tumor):
    spacing = tumor.GetSpacing()
    voxel_volume = np.prod(spacing)
    tumor_array = itk.GetArrayFromImage(tumor)
    num_voxels = np.sum(tumor_array > 0)
    volume = num_voxels * voxel_volume
    return volume

def calculate_intensity_difference(tumor1, tumor2):
    array1 = itk.GetArrayFromImage(tumor1)
    array2 = itk.GetArrayFromImage(tumor2)
    intensity_difference = np.sum(np.abs(array1 - array2))
    return intensity_difference

volume1 = calculate_volume(tumor1)
volume2 = calculate_volume(tumor2)

intensity_difference = calculate_intensity_difference(tumor1, tumor2)

print(f"Volume of Tumor 1: {volume1} mm3")
print(f"Volume of Tumor 2: {volume2} mm3")
print(f"Intensity Difference: {intensity_difference}")

def itk_to_vtk(itk_image):
    vtk_image = vtk.vtkImageData()
    itk_array = itk.GetArrayFromImage(itk_image)
    vtk_array = numpy_support.numpy_to_vtk(itk_array.ravel(), deep=True, array_type=vtk.VTK_FLOAT)
    vtk_image.SetDimensions(itk_image.GetLargestPossibleRegion().GetSize())
    vtk_image.SetSpacing(itk_image.GetSpacing())
    vtk_image.SetOrigin(itk_image.GetOrigin())
    vtk_image.GetPointData().SetScalars(vtk_array)
    return vtk_image

def visualize_individual_tumors(tumor1, tumor2):
    #create renderers and render window
    renderer1 = vtk.vtkRenderer()
    renderer2 = vtk.vtkRenderer()
    
    render_window = vtk.vtkRenderWindow()
    render_window.SetSize(1800, 900)
    render_window.AddRenderer(renderer1)
    render_window.AddRenderer(renderer2)
    
    render_window_interactor = vtk.vtkRenderWindowInteractor()
    render_window_interactor.SetRenderWindow(render_window)
    
    renderer1.SetViewport(0.0, 0.0, 0.5, 1.0)  # Left half
    renderer2.SetViewport(0.5, 0.0, 1.0, 1.0)  # Right half

    def add_actor(renderer, image, color, opacity=1.0):
        contour = vtk.vtkMarchingCubes()
        contour.SetInputData(image)
        contour.ComputeNormalsOn()
        contour.SetValue(0, 1)
        
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(contour.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(color)
        actor.GetProperty().SetOpacity(opacity)
        renderer.AddActor(actor)

    # convert ITK images to VTK
    vtk_tumor1 = itk_to_vtk(tumor1)
    vtk_tumor2 = itk_to_vtk(tumor2)
    
    add_actor(renderer1, vtk_tumor1, (1, 0, 0), opacity=1.0)
    add_actor(renderer2, vtk_tumor2, (0, 0, 1), opacity=1.0)
    
    renderer1.SetBackground(0., 0., 0.)  # background color black
    renderer2.SetBackground(0.1, 0., 0.)  # background color black
    
    # setup camera positions
    camera1 = renderer1.GetActiveCamera()
    camera1.SetPosition(414.5438659424792, -151.02336187356937, 410.064541307443)
    camera1.SetFocalPoint(0, 0, 0)
    camera1.SetViewUp(0, 1, 0)
    renderer1.SetActiveCamera(camera1)
    
    camera2 = renderer2.GetActiveCamera()
    camera2.SetPosition(414.5438659424792, -151.02336187356937, 410.064541307443)
    camera2.SetFocalPoint(0, 0, 0)
    camera2.SetViewUp(0, 1, 0)
    renderer2.SetActiveCamera(camera2)
    
    render_window.Render()
    render_window_interactor.Start()

visualize_individual_tumors(tumor1, tumor2)