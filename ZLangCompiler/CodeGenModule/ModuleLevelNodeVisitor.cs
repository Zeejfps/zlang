using LLVMSharp.Interop;
using ParserModule.Nodes;
using ParserModule.Visitors;

namespace CodeGenModule;

public sealed class ModuleLevelNodeVisitor : IModuleLevelNodeVisitor
{
    private readonly CodeGenerator _codeGenerator;

    public ModuleLevelNodeVisitor(CodeGenerator codeGenerator)
    {
        _codeGenerator = codeGenerator;
    }

    public void VisitFunctionDefinition(FunctionDefinitionNode node)
    {
        _codeGenerator.GenerateFunctionDefinition(node);
    }

    public void VisitStructDefinition(StructDefinitionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitExternFunctionDeclaration(ExternFunctionDeclarationNode node)
    {
        _codeGenerator.ExternFunctionGenerator.Generate(node);
    }
}